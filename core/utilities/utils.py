"""Small shared utilities used across the project."""

from typing import Any
import ast

from ..observability.logger import get_logger, ModuleLogger
logger: ModuleLogger = get_logger(__name__)


def parse_custom_text(val: Any) -> dict[str, Any]:
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str) and val:
        return ast.literal_eval(val)
    return {}


def first_present(d: dict[str, Any], keys: tuple[str, ...], default: Any) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default
