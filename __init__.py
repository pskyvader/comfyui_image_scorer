from typing import Any

def __getattr__(name: str) -> Any:
    if name == "NODE_CLASS_MAPPINGS":
        from .adapters.comfyui import NODE_CLASS_MAPPINGS as _m
        return _m
    if name == "NODE_DISPLAY_NAME_MAPPINGS":
        from .adapters.comfyui import NODE_DISPLAY_NAME_MAPPINGS as _m
        return _m
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
