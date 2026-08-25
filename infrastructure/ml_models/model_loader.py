import os
import threading
from typing import Any

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import huggingface_hub.constants as _hub_constants

_hub_constants.HF_HUB_OFFLINE = os.environ["HF_HUB_OFFLINE"] == "1"
_hub_constants.HF_HUB_DISABLE_TELEMETRY = os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"


def set_hub_offline(enabled: bool) -> None:
    """Flip HF hub offline mode after the import-time constants were mirrored.

    huggingface_hub computes ``HF_HUB_OFFLINE`` from the environment once at
    import; flipping ``os.environ`` alone has no effect afterwards.
    """
    value = "1" if enabled else "0"
    os.environ["HF_HUB_OFFLINE"] = value
    _hub_constants.HF_HUB_OFFLINE = value == "1"

import torch
from torch import nn
from safetensors.torch import load_file as load_safetensors
from torchvision import transforms
import timm
from ...core.configuration.settings import config
from ...core.filesystem.paths import mediapipe_models_dir
from sentence_transformers import SentenceTransformer
from transformers import (
    CLIPVisionConfig, CLIPVisionModel,
    CLIPImageProcessor, AutoImageProcessor, AutoModelForImageClassification,
)
from huggingface_hub import snapshot_download

from ...core.observability.logger import get_logger, ModuleLogger

logger: ModuleLogger = get_logger(__name__)


def _missing_model_error(description: str) -> RuntimeError:
    return RuntimeError(
        f"{description} is not downloaded. "
        "Run 'comfyui-scorer files download models' to download all models in prepare config."
    )


def _face_attributes_checkpoint_path(name: str) -> str:
    cache_dir = os.path.join(torch.hub.get_dir(), "checkpoints")
    return os.path.join(cache_dir, f"{name.replace('/', '_')}.safetensors")


class MultiTaskClipVisionModel(nn.Module):
    _VISION_CONFIG = CLIPVisionConfig(
        hidden_size=1024,
        intermediate_size=4096,
        num_attention_heads=16,
        num_hidden_layers=24,
        patch_size=14,
        image_size=224,
    )

    def __init__(self, num_labels: dict[str, int]) -> None:
        super().__init__()
        self.vision_model = CLIPVisionModel(self._VISION_CONFIG)
        hidden_size = self.vision_model.config.hidden_size
        self.age_head = nn.Linear(hidden_size, num_labels["age"])
        self.gender_head = nn.Linear(hidden_size, num_labels["gender"])
        self.race_head = nn.Linear(hidden_size, num_labels["race"])

    def forward(
        self, pixel_values: torch.Tensor
    ) -> dict[str, torch.Tensor]:
        outputs = self.vision_model(pixel_values=pixel_values)
        pooled = outputs.pooler_output
        return {
            "age": self.age_head(pooled),
            "gender": self.gender_head(pooled),
            "race": self.race_head(pooled),
        }


class ModelLoader:
    _IMAGENET_NORM = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ]
    )
    _CLIP_NORM = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5)),
        ]
    )

    def __init__(self):
        self.embedding_model: tuple[SentenceTransformer, int] | None = None
        self.vision_model_cache: dict[
            str, tuple[nn.Module, int, int, transforms.Compose]
        ] = {}
        self._model_info_cache: dict[str, dict[str, Any]] = {}
        self._hf_model_cache: dict[str, tuple[nn.Module, int, Any]] = {}
        self._hf_model_lock = threading.Lock()
        self.cnn_model: Any | None = None
        self.download_mode: bool = False
        self.prepare_config = config["prepare"]

    @staticmethod
    def _select_transform(name: str) -> transforms.Compose:
        if "clip" in name.lower():
            return ModelLoader._CLIP_NORM
        return ModelLoader._IMAGENET_NORM

    def load_vision_model(
        self, model_key: str
    ) -> tuple[nn.Module, int, int, transforms.Compose]:
        cached = self.vision_model_cache.get(model_key)
        if cached is not None:
            return cached

        vision_models: dict[str, dict[str, Any]] = self.prepare_config["vision_models"]
        if model_key not in vision_models:
            raise KeyError(
                f"Vision model key '{model_key}' not found in prepare_config. "
                f"Available: {list(vision_models.keys())}"
            )

        model_config = vision_models[model_key]
        device: str = model_config["device"]
        name: str = model_config["name"]
        output_dim: int = model_config["output_dim"]
        variable_input: bool = model_config["variable_input"]
        global_pool: str = model_config["global_pool"]

        if device != "cuda":
            raise RuntimeError("device not set to 'cuda'")

        logger.info("Loading Vision Model (%s): %s...", model_key, name)

        try:
            model: nn.Module = timm.create_model(
                name,
                pretrained=True,
                num_classes=0,
                global_pool=global_pool,
            )
        except OSError as e:
            raise _missing_model_error(f"Vision model '{name}'") from e

        model = model.eval()
        model.to(device)

        logger.info("Vision model '%s' loaded on device: %s", model_key, device)

        props = torch.cuda.get_device_properties(device)
        total_memory = int(props.total_memory)

        data_config = timm.data.resolve_model_data_config(model)
        input_size = data_config["input_size"]
        model_input_size = (input_size[2], input_size[1])

        transform = self._select_transform(name)
        if not variable_input:
            transform = transforms.Compose(
                [
                    transforms.Resize(model_input_size),
                    transform,
                ]
            )

        result = (model, output_dim, total_memory, transform)
        self.vision_model_cache[model_key] = result
        self._model_info_cache[model_key] = {
            "variable_input": variable_input,
            "input_size": model_input_size,
        }
        return result

    def get_model_info(self, model_key: str) -> dict[str, Any]:
        if model_key not in self.vision_model_cache:
            self.load_vision_model(model_key)
        return self._model_info_cache.get(model_key, {})

    def load_embedding_model(self) -> tuple[SentenceTransformer, int]:
        if self.embedding_model is not None:
            return self.embedding_model

        embedding_config = self.prepare_config["prompt_representation"]
        name: str = embedding_config["name"]
        output_dim: int = embedding_config["output_dim"]
        device: str = embedding_config["device"]

        if device != "cuda":
            raise RuntimeError("`clip_device` not set to 'cuda'")

        try:
            model = SentenceTransformer(
                name, device=device, local_files_only=not self.download_mode
            )
        except OSError as e:
            raise _missing_model_error(f"Embedding model '{name}'") from e

        self.embedding_model = (model, output_dim)
        return self.embedding_model

    def load_hf_vision_model(self, model_key: str) -> tuple[nn.Module, int, Any]:
        cached = self._hf_model_cache.get(model_key)
        if cached is not None:
            return cached

        with self._hf_model_lock:
            cached = self._hf_model_cache.get(model_key)
            if cached is not None:
                return cached
            result = self._load_hf_vision_model_impl(model_key)

        self._hf_model_cache[model_key] = result
        return result

    def _load_hf_vision_model_impl(self, model_key: str) -> tuple[nn.Module, int, Any]:
        attribute_models: dict[str, dict[str, Any]] = self.prepare_config["attribute_models"]
        if model_key not in attribute_models:
            raise KeyError(
                f"Attribute model key '{model_key}' not found in prepare_config. "
                f"Available: {list(attribute_models.keys())}"
            )

        model_config = attribute_models[model_key]
        name: str = model_config["name"]
        output_dim: int = model_config["output_dim"]
        device: str = model_config["device"]

        logger.info("Loading Attribute Model (%s): %s...", model_key, name)

        try:
            if model_key == "face_attributes":
                processor = CLIPImageProcessor.from_pretrained(name)
                num_labels = {"age": 9, "gender": 2, "race": 7}
                model = MultiTaskClipVisionModel(num_labels=num_labels)
                cache_path = _face_attributes_checkpoint_path(name)
                if not os.path.exists(cache_path):
                    if not self.download_mode:
                        raise _missing_model_error(f"Attribute model '{name}'")
                    torch.hub.download_url_to_file(
                        f"https://huggingface.co/{name}/resolve/main/model.safetensors",
                        cache_path,
                    )
                state_dict = load_safetensors(cache_path)
                model.load_state_dict(state_dict, strict=False)
                model = model.eval()
                model.to(device)
                logger.info("Attribute model '%s' loaded on device: %s", model_key, device)
                result = (model, output_dim, processor)
            elif model_key == "nsfw":
                processor = AutoImageProcessor.from_pretrained(name)
                model = AutoModelForImageClassification.from_pretrained(name)
                model = model.eval()
                model.to(device)
                logger.info("NSFW model '%s' loaded on device: %s", model_key, device)
                result = (model, output_dim, processor)
            else:
                raise KeyError(f"Unknown attribute model key: {model_key}")
        except OSError as e:
            raise _missing_model_error(f"Attribute model '{name}'") from e

        return result


def verify_models_present() -> None:
    prepare: dict = config["prepare"]
    missing: list[str] = []

    for key, model_config in prepare["vision_models"].items():
        name: str = model_config["name"]
        try:
            repo_id = timm.get_pretrained_cfg(name).hf_hub_id
            snapshot_download(repo_id, local_files_only=True)
        except (OSError, KeyError):
            missing.append(f"Vision model '{name}' ({key})")

    embedding_name: str = prepare["prompt_representation"]["name"]
    embedding_repo = (
        embedding_name
        if "/" in embedding_name
        else f"sentence-transformers/{embedding_name}"
    )
    try:
        snapshot_download(embedding_repo, local_files_only=True)
    except (OSError, KeyError):
        missing.append(f"Embedding model '{embedding_name}'")

    for key, model_config in prepare["attribute_models"].items():
        name = model_config["name"]
        if "url" in model_config:
            if not os.path.exists(os.path.join(mediapipe_models_dir, name)):
                missing.append(f"MediaPipe model '{name}'")
            continue
        try:
            snapshot_download(name, local_files_only=True)
            if key == "face_attributes" and not os.path.exists(
                _face_attributes_checkpoint_path(name)
            ):
                raise OSError
        except (OSError, KeyError):
            missing.append(f"Attribute model '{name}' ({key})")

    if missing:
        raise RuntimeError(
            "The following models in prepare config are not downloaded:\n- "
            + "\n- ".join(missing)
            + "\nRun 'comfyui-scorer files download models' to download all of them."
        )


def download_configured_models() -> None:
    loader = ModelLoader()
    loader.download_mode = True
    for key in loader.prepare_config["vision_models"]:
        loader.load_vision_model(key)
    loader.load_embedding_model()
    for key, model_config in loader.prepare_config["attribute_models"].items():
        if "url" not in model_config:
            loader.load_hf_vision_model(key)


model_loader = ModelLoader()
