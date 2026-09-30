import sys
from pathlib import Path

# ComfyUI puts its own root on sys.path before loading custom nodes, so `comfy`
# is importable there. The CLI and tests import this package directly, so mirror
# that step for the host ComfyUI checkout at ComfyUI/custom_nodes/<module>.
_COMFYUI_ROOT = Path(__file__).resolve().parents[2]
if str(_COMFYUI_ROOT) not in sys.path:
    sys.path.append(str(_COMFYUI_ROOT))

from .adapters.comfyui.node_registry import (  # noqa: E402
    NODE_CLASS_MAPPINGS as NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as NODE_DISPLAY_NAME_MAPPINGS,
)
