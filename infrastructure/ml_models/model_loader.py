import os
from typing import NamedTuple, cast

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


import numpy as np
import numpy.typing as npt
import torch
from torch import nn
from safetensors.torch import load_file as load_safetensors
from torchvision import transforms
from torchvision.transforms import Compose
import timm
from timm.data import resolve_model_data_config
import comfy.model_management
import comfy.system_memory
from comfy.model_patcher import ModelPatcher
from ...core.configuration.settings import (
    AttributeModelConfig,
    EmbeddingModelConfig,
    VisionModelConfig,
    config,
)
from ...core.filesystem.paths import mediapipe_models_dir
from sentence_transformers import SentenceTransformer
from transformers import (
    CLIPVisionConfig,
    CLIPVisionModel,
    CLIPImageProcessor,
    AutoImageProcessor,
    AutoModelForImageClassification,
)
from huggingface_hub import snapshot_download

from ...core.observability.logger import get_logger, ModuleLogger

from ...domain.ports.loading import AttributeOutput, ImageProcessor, ModelInfo

logger: ModuleLogger = get_logger(__name__)


def _load_device() -> torch.device:
    return cast("torch.device", comfy.model_management.text_encoder_device())


def _processor_input_size(processor: ImageProcessor, model_key: str) -> tuple[int, int]:
    """Read the resolution an attribute model's processor crops to.

    CLIP-style processors declare `crop_size` while ViT-style processors declare
    `size`, so both are read. A processor that declares neither is a
    configuration error rather than something to guess at.
    """
    for attribute in ("crop_size", "size"):
        box = getattr(processor, attribute, None)
        if isinstance(box, dict) and "height" in box and "width" in box:
            return int(box["height"]), int(box["width"])
    raise RuntimeError(
        f"Image processor for attribute model '{model_key}' declares no input "
        "size; expected crop_size or size to carry height and width"
    )


def _offload_device() -> torch.device:
    return cast(
        "torch.device", comfy.model_management.text_encoder_offload_device()
    )


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

    def forward(self, pixel_values: torch.Tensor) -> dict[str, torch.Tensor]:
        outputs = self.vision_model(pixel_values=pixel_values)
        pooled = outputs.pooler_output
        return {
            "age": self.age_head(pooled),
            "gender": self.gender_head(pooled),
            "race": self.race_head(pooled),
        }


class ClassificationOutput(NamedTuple):
    """Classifier logits in the shape `AttributeOutput` callers expect."""

    logits: torch.Tensor


class ImageClassificationModel(nn.Module):
    """Wraps a transformers classifier so ComfyUI's ModelPatcher can manage it.

    transformers models expose `device` as a read-only property, and
    ModelPatcher assigns to it while partially loading a model under memory
    pressure. Owning the classifier inside a plain module gives the patcher the
    settable attribute it expects.
    """

    def __init__(self, classifier: nn.Module) -> None:
        super().__init__()
        self.classifier = classifier

    def forward(self, **kwargs: torch.Tensor) -> ClassificationOutput:
        logits = self.classifier(**kwargs).logits
        return ClassificationOutput(logits)


class SentenceTransformerModel(nn.Module):
    """Wraps a SentenceTransformer so ComfyUI's ModelPatcher can manage it.

    SentenceTransformer exposes `device` as a read-only property and
    ModelPatcher assigns to it while partially loading, so the encoder is owned
    by a plain module that has the settable attribute the patcher expects.
    """

    def __init__(self, encoder: SentenceTransformer) -> None:
        super().__init__()
        self.encoder = encoder

    def encode(self, sentences: list[str]) -> npt.NDArray[np.float32]:
        return cast(
            "npt.NDArray[np.float32]",
            self.encoder.encode(sentences, convert_to_numpy=True),
        )


class ComfyVisionModel:
    """`VisionModel` wrapper that lets ComfyUI own device placement and VRAM."""

    def __init__(self, patcher: ModelPatcher) -> None:
        self.patcher = patcher

    @property
    def device(self) -> torch.device:
        return self.patcher.load_device

    def __call__(self, x: torch.Tensor) -> torch.Tensor:
        comfy.model_management.load_model_gpu(self.patcher)
        return self.patcher.model(x)


class ComfyEmbeddingModel:
    """`EmbeddingModel` wrapper that lets ComfyUI own device placement and VRAM."""

    def __init__(self, patcher: ModelPatcher) -> None:
        self.patcher = patcher

    def encode(self, sentences: list[str]) -> npt.NDArray[np.float32]:
        comfy.model_management.load_model_gpu(self.patcher)
        return cast(
            "npt.NDArray[np.float32]",
            self.patcher.model.encode(sentences),
        )


class ComfyAttributeModel:
    """`AttributeModel` wrapper that lets ComfyUI own device placement and VRAM."""

    def __init__(self, patcher: ModelPatcher) -> None:
        self.patcher = patcher

    @property
    def device(self) -> torch.device:
        return self.patcher.load_device

    def __call__(self, **kwargs: torch.Tensor) -> AttributeOutput:
        comfy.model_management.load_model_gpu(self.patcher)
        return cast("AttributeOutput", self.patcher.model(**kwargs))


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
        self.embedding_model: tuple[ComfyEmbeddingModel, int] | None = None
        self.vision_model_cache: dict[
            str, tuple[ComfyVisionModel, int, int, Compose]
        ] = {}
        self._model_info_cache: dict[str, ModelInfo] = {}
        self._hf_model_cache: dict[
            str, tuple[ComfyAttributeModel, int, ImageProcessor]
        ] = {}
        self.cnn_model: object | None = None
        self.download_mode: bool = False
        self.prepare_config = config["prepare"]

    @staticmethod
    def _select_transform(name: str) -> Compose:
        if "clip" in name.lower():
            return ModelLoader._CLIP_NORM
        return ModelLoader._IMAGENET_NORM

    def is_model_loaded(self, model_key: str, section: str = "vision_models") -> bool:
        """Whether a model for this key is already loaded and cached."""
        if section == "attribute_models":
            return model_key in self._hf_model_cache
        return model_key in self.vision_model_cache

    def load_vision_model_patcher(self, model_key: str) -> ModelPatcher:
        """Return the patcher behind a cached vision model for batch profiling."""
        return self.load_vision_model(model_key)[0].patcher

    def load_attribute_model_patcher(
        self, model_key: str
    ) -> tuple[ModelPatcher, int, int]:
        """Return the patcher and processor input size for an attribute model.

        Attribute models have a different memory profile from vision models, so
        batch profiling needs their own patcher and resolution rather than a
        borrowed one.
        """
        model, _output_dim, processor = self.load_hf_vision_model(model_key)
        height, width = _processor_input_size(processor, model_key)
        return model.patcher, height, width

    def load_vision_model(
        self, model_key: str
    ) -> tuple[ComfyVisionModel, int, int, Compose]:
        cached = self.vision_model_cache.get(model_key)
        if cached is not None:
            return cached

        vision_models: dict[str, VisionModelConfig] = self.prepare_config[
            "vision_models"
        ]
        if model_key not in vision_models:
            raise KeyError(
                f"Vision model key '{model_key}' not found in prepare_config. "
                f"Available: {list(vision_models.keys())}"
            )

        model_config = vision_models[model_key]
        name: str = model_config["name"]
        output_dim: int = model_config["output_dim"]
        variable_input: bool = model_config["variable_input"]
        global_pool: str = model_config["global_pool"]

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

        load_device = _load_device()
        offload_device = _offload_device()
        patcher = ModelPatcher(model, load_device, offload_device)

        logger.info("Vision model '%s' targets device: %s", model_key, load_device)

        total_memory = self._device_total_memory(load_device)

        data_config = cast(
            "dict[str, object]", resolve_model_data_config(model)
        )
        input_size = cast("tuple[int, int, int]", data_config["input_size"])
        model_input_size = (input_size[2], input_size[1])

        transform = self._select_transform(name)
        if not variable_input:
            transform = transforms.Compose(
                [
                    transforms.Resize(model_input_size),
                    transform,
                ]
            )

        result = (ComfyVisionModel(patcher), output_dim, total_memory, transform)
        self.vision_model_cache[model_key] = result
        self._model_info_cache[model_key] = ModelInfo(
            variable_input=variable_input, input_size=model_input_size
        )
        return result

    @staticmethod
    def _device_total_memory(device: torch.device) -> int:
        if device.type == "cuda":
            props = torch.cuda.get_device_properties(device)
            return int(props.total_memory)
        return int(comfy.system_memory.virtual_memory_total())

    def get_model_info(self, model_key: str) -> ModelInfo:
        if model_key not in self.vision_model_cache:
            self.load_vision_model(model_key)
        return self._model_info_cache[model_key]

    def load_embedding_model(self) -> tuple[ComfyEmbeddingModel, int]:
        if self.embedding_model is not None:
            return self.embedding_model

        embedding_config: EmbeddingModelConfig = self.prepare_config[
            "prompt_representation"
        ]
        name: str = embedding_config["name"]
        output_dim: int = embedding_config["output_dim"]

        try:
            st_model = SentenceTransformer(
                name, device="cpu", local_files_only=not self.download_mode
            )
        except OSError as e:
            raise _missing_model_error(f"Embedding model '{name}'") from e

        load_device = _load_device()
        offload_device = _offload_device()
        patcher = ModelPatcher(
            SentenceTransformerModel(st_model), load_device, offload_device
        )

        self.embedding_model = (ComfyEmbeddingModel(patcher), output_dim)
        return self.embedding_model

    def load_hf_vision_model(
        self, model_key: str
    ) -> tuple[ComfyAttributeModel, int, ImageProcessor]:
        cached = self._hf_model_cache.get(model_key)
        if cached is not None:
            return cached

        result = self._load_hf_vision_model_impl(model_key)
        self._hf_model_cache[model_key] = result
        return result

    def _load_hf_vision_model_impl(
        self, model_key: str
    ) -> tuple[ComfyAttributeModel, int, ImageProcessor]:
        attribute_models: dict[str, AttributeModelConfig] = self.prepare_config[
            "attribute_models"
        ]
        if model_key not in attribute_models:
            raise KeyError(
                f"Attribute model key '{model_key}' not found in prepare_config. "
                f"Available: {list(attribute_models.keys())}"
            )

        model_config = attribute_models[model_key]
        name: str = model_config["name"]
        output_dim: int = model_config["output_dim"]
        load_device = _load_device()
        offload_device = _offload_device()

        logger.info("Loading Attribute Model (%s): %s...", model_key, name)

        try:
            result: tuple[ComfyAttributeModel, int, ImageProcessor]
            if model_key == "face_attributes":
                processor = cast(
                    "ImageProcessor", CLIPImageProcessor.from_pretrained(name)
                )
                num_labels = {"age": 9, "gender": 2, "race": 7}
                model: nn.Module = MultiTaskClipVisionModel(num_labels=num_labels)
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
                logger.info(
                    "Attribute model '%s' targets device: %s", model_key, load_device
                )
                result = (
                    ComfyAttributeModel(ModelPatcher(model, load_device, offload_device)),
                    output_dim,
                    processor,
                )
            elif model_key == "nsfw":
                processor = cast(
                    "ImageProcessor", AutoImageProcessor.from_pretrained(name)
                )
                classifier = cast(
                    "nn.Module", AutoModelForImageClassification.from_pretrained(name)
                )
                model = ImageClassificationModel(classifier.eval())
                logger.info(
                    "NSFW model '%s' targets device: %s", model_key, load_device
                )
                result = (
                    ComfyAttributeModel(ModelPatcher(model, load_device, offload_device)),
                    output_dim,
                    processor,
                )
            else:
                raise KeyError(f"Unknown attribute model key: {model_key}")
        except OSError as e:
            raise _missing_model_error(f"Attribute model '{name}'") from e

        return result


def verify_models_present() -> None:
    prepare = config["prepare"]
    missing: list[str] = []

    vision_models: dict[str, VisionModelConfig] = prepare["vision_models"]
    for key, model_config in vision_models.items():
        name = model_config["name"]
        try:
            repo_cfg = timm.get_pretrained_cfg(name)
            repo_id = repo_cfg.hf_hub_id if repo_cfg is not None else None
            if repo_id is None:
                raise KeyError(name)
            snapshot_download(repo_id, local_files_only=True)
        except (OSError, KeyError):
            missing.append(f"Vision model '{name}' ({key})")

    embedding_config: EmbeddingModelConfig = prepare["prompt_representation"]
    embedding_name = embedding_config["name"]
    embedding_repo = (
        embedding_name
        if "/" in embedding_name
        else f"sentence-transformers/{embedding_name}"
    )
    try:
        snapshot_download(embedding_repo, local_files_only=True)
    except (OSError, KeyError):
        missing.append(f"Embedding model '{embedding_name}'")

    attribute_models: dict[str, AttributeModelConfig] = prepare["attribute_models"]
    for key, model_config in attribute_models.items():
        name = model_config["name"]
        if "url" in model_config:
            model_path = os.path.join(mediapipe_models_dir, name)
            if not os.path.exists(model_path):
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
