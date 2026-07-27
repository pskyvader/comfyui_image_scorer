from typing import Any


def cleanup(cleanup: bool = False, **kwargs: Any) -> int:
    from comfyui_image_scorer.infrastructure.persistence.comparisons_repository import clean_comparisons

    if cleanup:
        result = clean_comparisons()
    return 0


def deduplicate(deduplicate: bool = False, **kwargs: Any) -> int:
    return 0