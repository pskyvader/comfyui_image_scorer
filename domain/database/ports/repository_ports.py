"""Repository interface ports for domain isolation."""

from __future__ import annotations

from typing import Any, Protocol


class ImageRepository(Protocol):
    def get_image(self, filename: str) -> dict[str, Any] | None:
        ...

    def get_all_images(self) -> list[dict[str, Any]]:
        ...

    def get_image_count(self) -> int:
        ...

    def add_image(
        self,
        filename: str,
        score: float,
        comparison_count: int,
        prompt_tags: str | None,
        rating_mu: float,
        rating_sigma: float,
    ) -> bool:
        ...

    def update_image_rating_state(
        self,
        filename: str,
        score: float,
        rating_mu: float,
        rating_sigma: float,
        comparison_count: int,
        touch_timestamp: bool,
    ) -> bool:
        ...

    def update_image_tags(self, filename: str, prompt_tags: str) -> bool:
        ...

    def clear_all_images(self) -> int:
        ...

    def reset_all_image_ratings(self, score: float) -> bool:
        ...


class ComparisonRepository(Protocol):
    def add_comparison(
        self,
        filename_a: str,
        filename_b: str,
        winner: str,
        weight: float,
        transitive_depth: int,
        timestamp: str | None,
    ) -> int:
        ...

    def add_historical_comparison(
        self,
        filename_a: str,
        filename_b: str,
        winner: str,
        timestamp: str,
        weight: float,
        transitive_depth: int,
    ) -> int:
        ...

    def comparison_exists_for_pair(self, filename_a: str, filename_b: str) -> bool:
        ...

    def get_all_comparisons(self, weight: float | None = None) -> list[dict[str, Any]]:
        ...

    def get_total_comparisons(self) -> int:
        ...

    def get_skipped_comparison_count(self) -> int:
        ...

    def clean_comparisons(self) -> dict[str, int]:
        ...

    def get_images_with_only_wins(self) -> list[str]:
        ...

    def get_images_with_only_losses(self) -> list[str]:
        ...

    def clear_all_comparisons(self) -> int:
        ...


class PathResolver(Protocol):
    def sync_image_metadata_to_json(
        self,
        filename: str,
        score: float,
        rating_mu: float,
        rating_sigma: float,
        comparison_count: int,
        all_comparisons: list[dict[str, Any]] | None = None,
    ) -> bool:
        ...