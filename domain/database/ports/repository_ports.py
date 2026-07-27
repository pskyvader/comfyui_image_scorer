"""Repository interface ports for domain isolation."""

from __future__ import annotations

from typing import Any, Protocol


class ImageRepository(Protocol):
    def get_image(self, filename: str) -> dict[str, Any] | None:
        ...

    def get_all_images(self) -> list[dict[str, Any]]:
        ...

    def add_image(
        self,
        filename: str,
        score: float = 0.5,
        comparison_count: int = 0,
        prompt_tags: str | None = None,
        rating_mu: float = 25.0,
        rating_sigma: float = 25.0 / 3.0,
    ) -> bool:
        ...

    def update_image_rating_state(
        self,
        filename: str,
        score: float,
        rating_mu: float,
        rating_sigma: float,
        comparison_count: int,
    ) -> bool:
        ...


class ComparisonRepository(Protocol):
    def add_comparison(
        self,
        filename_a: str,
        filename_b: str,
        winner: str,
        impact_factor: float = 1.0,
        phase: str | None = None,
    ) -> bool:
        ...

    def get_all_comparisons(self) -> list[dict[str, Any]]:
        ...

    def get_total_comparisons(self) -> int:
        ...

    def comparison_exists_for_pair(self, filename_a: str, filename_b: str) -> bool:
        ...


class PathResolver(Protocol):
    def sync_image_metadata_to_json(self, filename: str) -> None:
        ...
