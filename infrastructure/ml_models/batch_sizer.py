from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast
import time

import torch
from torch import nn

import comfy.model_management
from comfy.model_patcher import ModelPatcher

from ...core.io.serialization import atomic_write_json, load_json
from ...core.observability.logger import get_logger

from ...core.configuration.settings import (
    AttributeModelConfig,
    VisionModelConfig,
    config,
)
from .model_loader import model_loader
from ...core.filesystem.paths import vectors_size_file

logger = get_logger(__name__)


@dataclass
class HistoryEntry:
    batch_size: int
    delta_memory: int
    timestamp: float


@dataclass
class ProfileData:
    model_name: str
    device_name: str
    device_id: str
    total_memory: int
    model_memory_bytes: int
    fixed_overhead: int | None = None
    pixel_cost: float | None = None
    r_squared: float | None = None
    history: dict[str, list[HistoryEntry]] = field(default_factory=lambda: {})


class BatchSizer:
    """Calibrates a batch size for one model by measuring real peak VRAM.

    Vision and attribute models are calibrated separately. They have different
    parameters and different call signatures, so sharing one number between
    them is what caused a face pass to run 764 images in a single forward.
    """

    def __init__(self, model_key: str, section: str = "vision_models") -> None:
        self._model_key = model_key
        self._section = section
        self._active: ProfileData | None = None
        self._ready: bool = False

    def _probe(self) -> tuple[ModelPatcher, int, int]:
        """Return the patcher to calibrate, plus the processor input size.

        Vision models are calibrated at whatever resolution the caller asks for,
        so their size comes back as zero.
        """
        if self._section == "attribute_models":
            return model_loader.load_attribute_model_patcher(self._model_key)
        return model_loader.load_vision_model_patcher(self._model_key), 0, 0

    def _run_probe(self, model: nn.Module, batch: torch.Tensor) -> None:
        if self._section == "attribute_models":
            model(pixel_values=batch)
        else:
            model(batch)

    def _ensure_session_profiled(self) -> None:
        _start = time.perf_counter()
        if self._ready:
            return

        data, _ = load_json(vectors_size_file, expect=dict)
        profiles_data: list[dict[str, Any]] = (
            data["profiles"] if data is not None and "profiles" in data else []
        )

        profiles: list[ProfileData] = []
        for profile_data in profiles_data:
            history_data: dict[str, list[dict[str, Any]]] = (
                profile_data["history"] if "history" in profile_data else {}
            )
            history = {
                key: [HistoryEntry(**entry) for entry in entries]
                for key, entries in history_data.items()
            }
            profile_fields: dict[str, Any] = {
                key: value
                for key, value in profile_data.items()
                if key not in ("history", "caps")
            }
            profiles.append(ProfileData(**profile_fields, history=history))

        vision_models: dict[str, VisionModelConfig] = config["prepare"][
            "vision_models"
        ]
        attribute_models: dict[str, AttributeModelConfig] = config["prepare"][
            "attribute_models"
        ]
        model_cfg: VisionModelConfig | AttributeModelConfig
        if self._section == "attribute_models":
            if self._model_key not in attribute_models:
                raise KeyError(
                    f"Attribute model key '{self._model_key}' not found in "
                    f"prepare_config. Available: {list(attribute_models)}"
                )
            model_cfg = attribute_models[self._model_key]
        else:
            if self._model_key not in vision_models:
                raise KeyError(
                    f"Vision model key '{self._model_key}' not found in "
                    f"prepare_config. Available: {list(vision_models)}"
                )
            model_cfg = vision_models[self._model_key]
        model_name: str = model_cfg["name"]
        device_id: str = model_cfg["device"]
        device_name = torch.cuda.get_device_name(device_id)
        total_mem = int(torch.cuda.get_device_properties(device_id).total_memory)

        self._active = None
        for profile in profiles:
            if profile.model_name == model_name and profile.device_name == device_name:
                self._active = profile
                break

        if self._active is None:
            self._active = ProfileData(
                model_name=model_name,
                device_name=device_name,
                device_id=device_id,
                total_memory=total_mem,
                model_memory_bytes=0,
            )

        # Re-measure only when this sizer's model is already resident; otherwise
        # keep what the profile recorded and let the first profiling pass
        # refresh it.
        if model_loader.is_model_loaded(self._model_key, self._section):
            self._active.model_memory_bytes = int(
                torch.cuda.memory_allocated(self._active.device_id)
            )

        self._ready = True

    @staticmethod
    def _resolution_key(width: int, height: int) -> str:
        _start = time.perf_counter()
        a, b = (width, height) if width <= height else (height, width)
        result = f"{a}x{b}"

        return result

    def _calibration_resolution(self, width: int, height: int) -> tuple[int, int]:
        """The resolution this sizer actually calibrates at.

        Attribute models are profiled at the resolution their own processor
        crops to, not at whatever the caller asked for.
        """
        if self._section == "attribute_models":
            _patcher, probe_height, probe_width = self._probe()
            return probe_width, probe_height
        return width, height

    def get(
        self,
        width: int,
        height: int,
        rebuild: bool,
        bound: int | None = None,
    ) -> int:
        _start = time.perf_counter()
        self._ensure_session_profiled()
        profile = self._active
        assert profile is not None

        width, height = self._calibration_resolution(width, height)
        key = self._resolution_key(width, height)
        if key in profile.history and not rebuild:
            result = max(entry.batch_size for entry in profile.history[key])
            if bound is not None:
                result = min(result, bound)
            # A recorded batch was measured against whatever else was resident
            # at the time. Re-check it against current headroom so a stale
            # profile cannot hand back a size that no longer fits.
            if not self._fits_now(key, result, profile):
                logger.info(
                    f"Recorded batch size {result} for {key} no longer fits "
                    f"({self._model_key}); re-profiling"
                )
                result = self._profile_new_resolution(width, height, True, bound)
                if bound is not None:
                    result = min(result, bound)

            return result

        result = self._profile_new_resolution(width, height, rebuild, bound)
        if bound is not None:
            result = min(result, bound)

        return result

    def _profile_new_resolution(
        self,
        width: int,
        height: int,
        rebuild: bool,
        bound: int | None,
    ) -> int:
        _start = time.perf_counter()
        profile = self._active
        assert profile is not None

        key = self._resolution_key(width, height)
        if key not in profile.history:
            profile.history[key] = []

        if self._section == "attribute_models":
            patcher, _probe_height, _probe_width = self._probe()
        else:
            patcher = model_loader.load_vision_model_patcher(self._model_key)
        if patcher.load_device.type != "cuda":
            return min(1, bound if bound is not None else 1)

        comfy.model_management.load_model_gpu(patcher)
        model = patcher.model
        if not self._fully_resident(model):
            # Probing a split model cannot work: some weights sit on the
            # offload device while the probe tensor is on the GPU, and a
            # forward through it faults rather than raising. Report it instead
            # of letting every candidate "fail" and implying a size problem.
            logger.warning(
                f"Model '{self._model_key}' is split across devices after "
                "loading, so it cannot be batch profiled; using a batch of 1"
            )
            return min(1, bound if bound is not None else 1)
        profile.model_memory_bytes = int(
            torch.cuda.memory_allocated(patcher.load_device)
        )

        device_id = profile.device_id
        available = int(profile.total_memory) - profile.model_memory_bytes

        if rebuild and profile.history[key]:
            best = max(entry.batch_size for entry in profile.history[key])
            if bound is not None:
                best = min(best, bound)
            result = self._evaluate_candidate(
                model=model,
                profile=profile,
                key=key,
                candidate=best,
                width=width,
                height=height,
                device_id=device_id,
            )
            if result is not None:

                return result
            low, high = 1, best - 1
        else:
            high = 1000
            if profile.pixel_cost is not None:
                per_image = profile.pixel_cost * width * height * 3
                fixed = profile.fixed_overhead or 0
                if per_image > 0:
                    high = max(1, int((available - fixed) / per_image) * 2)
            if bound is not None:
                high = min(high, bound)
            low = 1

        last_success = 0
        while low <= high:
            mid: int = (low + high) // 2
            if mid == last_success:
                break

            result = self._evaluate_candidate(
                model=model,
                profile=profile,
                key=key,
                candidate=mid,
                width=width,
                height=height,
                device_id=device_id,
            )
            if result is None:
                high = mid - 1
            else:
                last_success = result
                low = mid + 1

        result = max(last_success, 1)

        old_fixed = profile.fixed_overhead
        old_pixel = profile.pixel_cost
        self._fit_model()
        if (
            old_fixed is not None
            and old_pixel is not None
            and profile.fixed_overhead is not None
            and profile.pixel_cost is not None
        ):
            fixed_shift = abs(profile.fixed_overhead - old_fixed) / max(
                abs(old_fixed), 1
            )
            pixel_shift = abs(profile.pixel_cost - old_pixel) / max(
                abs(old_pixel), 1e-12
            )
            if fixed_shift > 0.1 or pixel_shift > 0.1:
                logger.warning(
                    "model parameters shifted significantly after rebuild "
                    f"(fixed: {old_fixed} -> {profile.fixed_overhead}, "
                    f"pixel: {old_pixel} -> {profile.pixel_cost})"
                )

        self._save_cache()

        return result

    def _evaluate_candidate(
        self,
        *,
        model: nn.Module,
        profile: ProfileData,
        key: str,
        candidate: int,
        width: int,
        height: int,
        device_id: str,
    ) -> int | None:
        result = None
        logger.debug(
            f"Evaluating batch size {candidate} for resolution {width}x{height}"
        )
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device_id)
        # Probe on the device and in the dtype the model actually holds.
        # ComfyUI partially offloads a model when memory is tight, so building
        # the probe from config alone puts it on a different device than some of
        # the weights, and the failure looks like a size problem rather than a
        # placement one.
        first_parameter = next(model.parameters())
        batch_tensor = torch.zeros(
            (candidate, 3, height, width),
            device=first_parameter.device,
            dtype=first_parameter.dtype,
        )
        try:
            model.eval()
            self._run_probe(model, batch_tensor)
            torch.cuda.synchronize(device_id)

            peak = int(torch.cuda.max_memory_allocated(device_id))
            delta = peak - profile.model_memory_bytes
            if peak < self._available_for(profile):
                profile.history[key].append(
                    HistoryEntry(
                        batch_size=candidate,
                        delta_memory=delta,
                        timestamp=time.time(),
                    )
                )
                result = candidate
        except Exception as e:
            logger.warning(
                f"batch size {candidate} for resolution {width}x{height} failed with error: {e}"
            )
        finally:
            del batch_tensor
            torch.cuda.empty_cache()
        return result

    @staticmethod
    def _fully_resident(model: nn.Module) -> bool:
        """True when every parameter sits on the same device."""
        devices = {parameter.device for parameter in model.parameters()}
        return len(devices) == 1

    def _available_for(self, profile: ProfileData) -> int:
        """Memory a probe may claim, given what is already resident.

        Measuring against total device memory is how a batch gets recorded that
        fits in isolation but not once the rest of the pipeline is loaded, so
        the threshold is what ComfyUI reports as free right now.
        """
        free = cast("int", comfy.model_management.get_free_memory(profile.device_id))
        return min(profile.total_memory, free)

    def _fits_now(self, key: str, candidate: int, profile: ProfileData) -> bool:
        """True when a recorded batch still fits in current headroom.

        Uses the delta measured for that exact batch size, so this is an
        estimate rather than a fresh probe. When it says no, the caller
        re-profiles for real rather than guessing.
        """
        if candidate <= 1:
            return True
        recorded = [
            entry
            for entry in profile.history.get(key, [])
            if entry.batch_size == candidate
        ]
        if not recorded:
            return False
        entry = max(recorded, key=lambda e: e.batch_size)
        model_memory = int(torch.cuda.memory_allocated(profile.device_id))
        return (model_memory + entry.delta_memory) < self._available_for(profile)

    def _fit_model(self) -> None:
        _start = time.perf_counter()
        profile = self._active
        assert profile is not None

        x_values: list[float] = []
        y_values: list[float] = []
        for res_key, entries in profile.history.items():
            width_str, height_str = res_key.split("x")
            width = int(width_str)
            height = int(height_str)
            for entry in entries:
                x_values.append(float(entry.batch_size * width * height * 3))
                y_values.append(float(entry.delta_memory))

        count = len(x_values)
        if count < 2:
            profile.fixed_overhead = None
            profile.pixel_cost = None
            profile.r_squared = None

            return

        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xx = sum(value * value for value in x_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        denom = count * sum_xx - sum_x * sum_x
        if denom == 0:
            profile.fixed_overhead = None
            profile.pixel_cost = None
            profile.r_squared = None

            return

        pixel_cost = (count * sum_xy - sum_x * sum_y) / denom
        fixed_overhead = (sum_y - pixel_cost * sum_x) / count
        mean_y = sum_y / count
        ss_res = sum(
            (y - (fixed_overhead + pixel_cost * x)) ** 2
            for x, y in zip(x_values, y_values)
        )
        ss_tot = sum((y - mean_y) ** 2 for y in y_values)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        profile.fixed_overhead = int(round(fixed_overhead))
        profile.pixel_cost = pixel_cost
        profile.r_squared = r_squared

    def _save_cache(self) -> None:
        _start = time.perf_counter()
        profile = self._active
        if profile is None:

            return

        loaded, _ = load_json(vectors_size_file, expect=dict)
        data: dict[str, Any] = loaded if loaded is not None else {}
        if "profiles" not in data:
            data["profiles"] = []

        history_payload: dict[str, list[dict[str, object]]] = {}
        for res_key, entries in profile.history.items():
            history_payload[res_key] = [
                {
                    "batch_size": entry.batch_size,
                    "delta_memory": entry.delta_memory,
                    "timestamp": entry.timestamp,
                }
                for entry in entries
            ]

        profile_payload: dict[str, object] = {
            "model_name": profile.model_name,
            "device_name": profile.device_name,
            "device_id": profile.device_id,
            "total_memory": profile.total_memory,
            "model_memory_bytes": profile.model_memory_bytes,
            "fixed_overhead": profile.fixed_overhead,
            "pixel_cost": profile.pixel_cost,
            "r_squared": profile.r_squared,
            "history": history_payload,
        }

        existing_profiles: list[dict[str, Any]] = data["profiles"]
        for index, existing in enumerate(existing_profiles):
            if (
                existing["model_name"] == profile.model_name
                and existing["device_name"] == profile.device_name
            ):
                existing_profiles[index] = profile_payload
                break
        else:
            existing_profiles.append(profile_payload)

        atomic_write_json(vectors_size_file, data, indent=4)
