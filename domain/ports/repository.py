"""Repository interface ports for domain isolation.

Moved from ``domain/database/ports/repository_ports.py``. All protocols use
concrete return types — no ``Any``. Callers should import from this module.
"""

from __future__ import annotations

from typing import NotRequired, Protocol, TypedDict


class ImageRow(TypedDict):
    """One persisted image record as read from the images table."""

    filename: str
    score: float
    rating_mu: float
    rating_sigma: float
    comparison_count: int
    last_compared_at: str | None
    ranking_generation: int
    prompt_tags: str | None


class ComparisonRow(TypedDict):
    """One comparison edge crossing the repository, proxy, and service boundary.

    ``timestamp`` and ``id`` are present on persisted rows; graph-only edges and
    training rows carry the three identity fields alone.
    """

    filename_a: str
    filename_b: str
    winner: str
    timestamp: NotRequired[str]
    id: NotRequired[int]


# filename, score, rating_mu, rating_sigma, comparison_count
RatingStateUpdate = tuple[str, float, float, float, int]


class ImageRowForInsert(TypedDict):
    """One image record to insert, without the read-only database columns."""

    filename: str
    score: float
    rating_mu: float
    rating_sigma: float
    comparison_count: int
    prompt_tags: str | None


class ImageRepository(Protocol):
    def find_node(self, filename: str) -> ImageRow | None: ...

    def list_nodes(self) -> list[ImageRow]: ...

    def get_image_count(self) -> int: ...

    def add_image(
        self,
        filename: str,
        score: float,
        comparison_count: int,
        prompt_tags: str | None,
        rating_mu: float,
        rating_sigma: float,
    ) -> bool: ...

    def update_image_rating_state(
        self,
        filename: str,
        score: float,
        rating_mu: float,
        rating_sigma: float,
        comparison_count: int,
        touch_timestamp: bool,
    ) -> bool: ...

    def add_images_bulk(self, rows: list[ImageRowForInsert]) -> int: ...

    def update_image_rating_states_bulk(
        self, rows: list[RatingStateUpdate]
    ) -> int: ...

    def update_image_tags(self, filename: str, prompt_tags: str) -> bool: ...

    def clear_all_images(self) -> int: ...

    def reset_all_image_ratings(self, score: float) -> bool: ...


class ComparisonRepository(Protocol):
    def add_comparison(
        self,
        filename_a: str,
        filename_b: str,
        winner: str,
        timestamp: str | None,
    ) -> int: ...

    def add_comparisons_bulk(self, rows: list[ComparisonRow]) -> list[int]: ...

    def comparison_exists_for_pair(self, filename_a: str, filename_b: str) -> bool: ...

    def list_links(self) -> list[ComparisonRow]: ...

    def get_total_comparisons(self) -> int: ...

    def clean_comparisons(self) -> dict[str, int]: ...

    def get_nodes_with_only_wins(self) -> list[str]: ...

    def get_nodes_with_only_losses(self) -> list[str]: ...

    def clear_all_comparisons(self) -> int: ...


class PathResolver(Protocol):
    def sync_image_metadata_to_json(
        self,
        filename: str,
        score: float,
        rating_mu: float,
        rating_sigma: float,
        comparison_count: int,
        all_comparisons: list[ComparisonRow] | None = None,
    ) -> bool: ...
