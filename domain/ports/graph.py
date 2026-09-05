"""Domain port defining the CrystalGraph abstract interface.

All concrete graph implementations (e.g. application.services.graph_service.CrystalGraph)
must satisfy this protocol exactly. Return types are concrete proxy types — no ``Any``.
"""

from __future__ import annotations

from typing import Optional

from ...domain.graph.component_proxy import ComponentProxy
from ...domain.graph.link_proxy import LinkProxy
from ...domain.graph.chain_proxy import ChainProxy
from ...domain.graph.node_proxy import NodeProxy


class CrystalGraphPort:
    """Abstract interface for graph-level selection memory accessors.

    Callers use node/link/proxy vocabulary (NodeProxy, LinkProxy, ChainProxy,
    ComponentProxy). No caller outside CrystalGraph imports repositories or
    accesses database tables directly.
    """

    # -- Node lookups -------------------------------------------------------

    def get_node(self, node_id: str | None) -> NodeProxy | None: ...

    def get_all_nodes(
        self, only_top: bool = False, only_bottom: bool = False
    ) -> list[NodeProxy]: ...

    def get_node_count(self) -> int: ...

    # -- Chain lookups ------------------------------------------------------

    def get_chain(
        self, node_id: str | None = None, chain_id: int | None = None
    ) -> ChainProxy | None: ...

    def get_all_chains(
        self, min_length: int = 0, sort_order: str = "desc"
    ) -> list[ChainProxy]: ...

    # -- Component lookups --------------------------------------------------

    def get_component(
        self,
        node_id: str | None = None,
        component_id: int | None = None,
        chain_id: int | None = None,
    ) -> ComponentProxy | None: ...

    def get_all_components(self) -> list[ComponentProxy]: ...

    # -- Links --------------------------------------------------------------

    def get_all_links(self) -> list[LinkProxy]: ...

    def get_link_count(self) -> int: ...

    def link_exists_between(self, a: str, b: str) -> bool: ...

    # -- Stats --------------------------------------------------------------

    def get_graph_stats(self) -> dict[str, int]: ...

    # -- Selection working memory                                         #

    def is_cache_stale(self) -> bool: ...

    def reset_selection_state(self) -> None: ...

    def get_skip_before(self) -> int: ...

    def set_skip_before(self, value: int) -> None: ...

    def get_existing_pairs(self) -> set[tuple[str, str]]: ...

    def set_existing_pairs(self, pairs: set[tuple[str, str]]) -> None: ...

    def get_recent_chain_ids(self) -> list[int]: ...

    def set_recent_chain_ids(self, chain_ids: list[int]) -> None: ...

    # -- Image snapshot cache                                             #

    def get_images_snapshot(self) -> list[dict[str, object]] | None: ...

    def set_images_snapshot(self, images: list[dict[str, object]]) -> None: ...

    def invalidate_images_snapshot(self) -> None: ...

    # -- Repository facade                                                #

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

    def update_image_tags(self, filename: str, prompt_tags: str) -> None: ...

    def clear_all_images(self) -> None: ...

    def reset_all_image_ratings(self, score: float) -> None: ...

    def get_total_comparisons(self) -> int: ...

    def get_nodes_with_only_wins(self) -> list[str]: ...

    def get_nodes_with_only_losses(self) -> list[str]: ...

    def comparison_exists_for_pair(self, filename_a: str, filename_b: str) -> bool: ...

    def add_comparison(
        self,
        filename_a: str,
        filename_b: str,
        winner: str,
        timestamp: str,
    ) -> int: ...

    def apply_comparison(self, winner: str, loser: str) -> None: ...

    def clean_comparisons(self) -> None: ...

    def clear_all_comparisons(self) -> None: ...

    def get_chains_map(self) -> dict[int, dict[int, tuple[ChainProxy, list[tuple[NodeProxy, bool]]]]]: ...