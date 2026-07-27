"""ComfyUI adapter — exports NODE_CLASS_MAPPINGS and NODE_DISPLAY_NAME_MAPPINGS dicts for automatic custom-node registration when ComfyUI loads this package."""

from comfyui_image_scorer.adapters.comfyui.node_registry import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
