"""Repository interface ports for domain isolation."""

from __future__ import annotations

from typing import Protocol


class ImageRepository(Protocol):
    def find_node(self, filename: str) -> dict[str, object] | None:
        ...

    def list_nodes(self) -> list[dict[str, object]]:
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
        timestamp: str | None,
    ) -> int:
        ...

    def add_historical_comparison(
        self,
        filename_a: str,
        filename_b: str,
        winner: str,
        timestamp: str,
    ) -> int:
        ...

    def comparison_exists_for_pair(self, filename_a: str, filename_b: str) -> bool:
        ...

    def list_links(self) -> list[dict[str, object]]:
        ...

    def get_total_comparisons(self) -> int:
        ...

    def clean_comparisons(self) -> dict[str, int]:
        ...

    def get_nodes_with_only_wins(self) -> list[str]:
        ...

    def get_nodes_with_only_losses(self) -> list[str]:
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
        all_comparisons: list[dict[str, object]] | None = None,
    ) -> bool:
        ...
