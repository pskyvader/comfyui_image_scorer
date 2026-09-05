"""Application service owning graph-level selection memory accessors."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from tqdm import tqdm
import time


from ...core.observability.logger import get_logger, ModuleLogger

from ...domain.ports.repository import ImageRepository, ComparisonRepository
from ...domain.graph.chain_manager import ChainManager
from ...domain.graph.node_proxy import NodeProxy
from ...domain.graph.chain_proxy import ChainProxy
from ...domain.graph.component_proxy import ComponentProxy
from ...domain.graph.link_proxy import LinkProxy
from ...domain.ports.cache import CacheProvider
from ...domain.ports.files import FilePort

logger: ModuleLogger = get_logger(__name__)

# Type aliases for chain mapping structures
NodeTuple = tuple[NodeProxy, bool]
ChainTuple = tuple[ChainProxy, list[NodeTuple]]
ChainDict = dict[int, ChainTuple]


class CrystalGraph:
    """Main graph API. All access through get_* methods returning proxy objects."""

    def __init__(
        self,
        image_repo: ImageRepository | None = None,
        comparison_repo: ComparisonRepository | None = None,
        cache: CacheProvider | None = None,
        file_port: FilePort | None = None,
    ) -> None:
        self._chain: ChainManager = ChainManager()
        self._images: dict[str, dict[str, Any]] = {}
        self._chain_map: dict[int, ChainDict] | None = None
        self._rebuilding: bool = False
        self._creating_chain_map: bool = False
        self._image_repo = image_repo
        self._comparison_repo = comparison_repo
        self._cache = cache
        self._file_port = file_port
        self._loaded: bool = False
        # Selection working memory (#49/#50): replaces the former module-level
        # _skip_before/_existing_pairs/_last_chains_index globals.
        self._skip_before: int = 0
        self._existing_pairs: set[tuple[str, str]] = set()
        self._recent_chain_ids: list[int] = []

    def _make_node(self, node_id: str) -> NodeProxy:
        return NodeProxy(self._chain, node_id, self._images.get(node_id))

    def _make_chain(self, chain_id: int, nodes: list[str]) -> ChainProxy:
        return ChainProxy(self._chain, chain_id, nodes)

    def _make_component(self, component_id: int) -> ComponentProxy:
        return ComponentProxy(self._chain, component_id)

    def _make_link(self, record: Any) -> LinkProxy:
        return LinkProxy(self._chain, record)

    def read_json_file(self, path: str) -> dict[str, Any]:
        if self._file_port is None:
            raise RuntimeError("No filesystem port provided")
        return self._file_port.read_json(path)

    def write_json_file(self, path: str, data: dict[str, Any]) -> None:
        if self._file_port is None:
            raise RuntimeError("No filesystem port provided")
        self._file_port.write_json(path, data)

    # -- Lifecycle ------------------------------------------------------
    def is_loaded(self) -> bool:
        """Return whether this graph has been explicitly built from data."""
        return self._loaded

    def get_node_chain_length(self, filename: str) -> int:
        main: tuple[int, list[str]] | None = self._chain.get_node_main_chain(filename)
        if main is None:
            return 0
        return len(main[1])

    def get_main_chain_member_count(self, chain_id: int) -> int:
        """Return how many nodes have ``chain_id`` as their main chain."""
        count = 0
        for node in self.get_all_nodes():
            main = self._chain.get_node_main_chain(node.filename)
            if main is not None and main[0] == chain_id:
                count += 1
        return count

    def rebuild_from_database(
        self,
        images: list[dict[str, Any]] | None = None,
        comparisons: list[dict[str, Any]] | None = None,
    ) -> None:
        _start = time.perf_counter()
        if self._rebuilding:
            logger.warning("Already rebuilding, skipping nested call")
            return
        self._rebuilding = True
        logger.info("Rebuilding chain from database...")

        if images is None:
            if self._image_repo is None:
                self._rebuilding = False
                raise RuntimeError("No ImageRepository provided and no images passed")
            images = self._image_repo.list_nodes()
        if comparisons is None:
            if self._comparison_repo is None:
                self._rebuilding = False
                raise RuntimeError(
                    "No ComparisonRepository provided and no comparisons passed"
                )
            comparisons = self._comparison_repo.list_links()

        self._images = {img["filename"]: img for img in images}
        self._chain.set_db_comparison_count(len(comparisons))
        self._chain.set_built_at(datetime.now(timezone.utc))

        all_filenames: set[str] = set(self._images.keys())
        comp: dict[str, Any]
        for comp in comparisons:
            all_filenames.add(comp["filename_a"])
            all_filenames.add(comp["filename_b"])

        self._chain.build(comparisons, all_filenames=all_filenames)
        self._loaded = True
        self._chain_map = None  # chain map will be rebuilt lazily
        # self.get_chains_map()
        self._rebuilding = False
        logger.info("rebuild from database complete", start_timer=_start)

    def apply_comparison(self, winner: str, loser: str) -> None:
        self._chain.apply_comparison(winner, loser)

    def add_link(
        self,
        filename_a: str,
        filename_b: str,
        winner: str,
        timestamp: str,
    ) -> int:
        if self._comparison_repo is None:
            raise RuntimeError("No ComparisonRepository provided")
        link_id = self._comparison_repo.add_comparison(
            filename_a=filename_a,
            filename_b=filename_b,
            winner=winner,
            timestamp=timestamp,
        )
        loser = filename_b if winner == filename_a else filename_a
        self._chain.apply_comparison(winner, loser)
        history = self._chain.get_comparison_history()
        record = next(
            item
            for item in reversed(history)
            if item.winner == winner and item.loser == loser
        )
        record.id = link_id
        record.timestamp = timestamp
        return link_id

    # -- Selection working memory (#49/#50) ------------------------------

    def reset_selection_state(self) -> None:
        self._skip_before = 0
        self._existing_pairs = set()

    def get_skip_before(self) -> int:
        return self._skip_before

    def set_skip_before(self, value: int) -> None:
        self._skip_before = value

    def get_existing_pairs(self) -> set[tuple[str, str]]:
        return self._existing_pairs

    def set_existing_pairs(self, pairs: set[tuple[str, str]]) -> None:
        self._existing_pairs = pairs

    def get_recent_chain_ids(self) -> list[int]:
        return self._recent_chain_ids

    def set_recent_chain_ids(self, chain_ids: list[int]) -> None:
        self._recent_chain_ids = chain_ids

    # -- Images snapshot cache (replaces domain/comparison/state.py) -----

    def get_images_snapshot(self) -> list[dict[str, Any]] | None:
        if self._cache is None:
            return None
        return self._cache.get("images")

    def set_images_snapshot(self, images: list[dict[str, Any]]) -> None:
        assert self._cache is not None
        self._cache.set("images", images)

    def invalidate_images_snapshot(self) -> None:
        if self._cache is not None:
            self._cache.invalidate("images")

    # -- Cache ----------------------------------------------------------

    def is_cache_stale(self) -> bool:
        if self._chain.get_built_at() is None:
            return True
        if self._comparison_repo is not None:
            if (
                self._comparison_repo.get_total_comparisons()
                != self._chain.get_db_comparison_count()
            ):
                # logger.debug(
                #     f"stale: total comparisons: {self._comparison_repo.get_total_comparisons()}"
                #     f", db comparisons: {self._chain.get_db_comparison_count()}"
                # )
                return True
        return False

    # -- Node lookups ---------------------------------------------------

    def get_node(self, node_id: str | None) -> NodeProxy | None:
        if node_id is None or node_id not in self._chain.get_all_filenames():
            return None
        return self._make_node(node_id)

    def get_all_nodes(
        self, only_top: bool = False, only_bottom: bool = False
    ) -> list[NodeProxy]:
        if only_top and only_bottom:
            raise ValueError("only_top and only_bottom cannot both be True")
        if only_top:
            return [self._make_node(n) for n in self._chain.get_top_nodes()]
        if only_bottom:
            return [self._make_node(n) for n in self._chain.get_bottom_nodes()]
        return [self._make_node(n) for n in self._chain.get_all_filenames()]

    # -- Chain lookups --------------------------------------------------

    def get_chain(
        self, node_id: str | None = None, chain_id: int | None = None
    ) -> ChainProxy | None:
        if (node_id is None) == (chain_id is None):
            raise ValueError("Exactly one of node_id or chain_id is required")
        if node_id is not None:
            if node_id not in self._chain.get_all_filenames():
                return None
            main: tuple[int, list[str]] | None = self._chain.get_node_main_chain(
                node_id
            )
            if main is None:
                return None
            return self._make_chain(main[0], main[1])
        if chain_id is not None:
            chains: dict[int, list[str]] = self._chain.get_chains()
            if chain_id < 0 or chain_id not in chains:
                return None
            return self._make_chain(chain_id, chains[chain_id])
        return None

    def get_all_chains(
        self,
        min_length: int = 0,
        sort_order: str = "desc",
    ) -> list[ChainProxy]:
        result = [
            self._make_chain(chain_id, nodes)
            for chain_id, nodes in self._chain.get_chains().items()
        ]
        if min_length > 0:
            result = [chain for chain in result if min_length <= chain.length]
        result.sort(key=lambda chain: chain.length, reverse=(sort_order != "asc"))
        return result

    def get_component(
        self,
        node_id: str | None = None,
        component_id: int | None = None,
        chain_id: int | None = None,
    ) -> ComponentProxy | None:
        n_specified: int = sum(
            1 for x in (node_id, component_id, chain_id) if x is not None
        )
        if n_specified != 1:
            raise ValueError(
                "Exactly one of node_id, component_id, or chain_id is required"
            )
        if node_id is not None:
            cid = self._chain.get_component_id(node_id)
            if cid is None:
                return None
            return self._make_component(cid)
        if component_id is not None:
            if component_id not in self._chain.get_component_ids():
                return None
            return self._make_component(component_id)
        if chain_id is not None:
            chain: ChainProxy | None = self.get_chain(chain_id=chain_id)
            if chain is None or not chain.nodes:
                return None
            component_id = self._chain.get_component_id(chain.nodes[0].filename)
            if component_id is None:
                return None
            return self._make_component(component_id)
        return None

    def get_all_components(self) -> list[ComponentProxy]:
        return [
            self._make_component(component_id)
            for component_id in self._chain.get_component_ids()
        ]

    # -- Links ----------------------------------------------------------

    def get_all_links(self) -> list[LinkProxy]:
        records: list[_ComparisonRecord] = self._chain.get_comparison_history()
        logger.debug(f"records: {len(records)}")
        return [self._make_link(record) for record in records]

    def get_link_count(self) -> int:
        return len(self._chain.get_comparison_history())

    def get_node_count(self) -> int:
        return len(self._chain.get_all_filenames())

    def get_winner_only_nodes(self) -> list[NodeProxy]:
        return [self._make_node(n) for n in self._chain.get_nodes_with_only_wins()]

    def get_loser_only_nodes(self) -> list[NodeProxy]:
        return [self._make_node(n) for n in self._chain.get_nodes_with_only_losses()]

    def link_exists_between(self, a: str, b: str) -> bool:
        return self._chain.link_exists_between(a, b)

    # -- Stats ----------------------------------------------------------

    def get_graph_stats(self) -> dict[str, Any]:
        chains: list[list[str]] = list((self._chain.get_chains()).values())
        built_at: datetime | None = self._chain.get_built_at()
        return {
            "total_images": len(self._images) or len(self._chain.get_all_filenames()),
            "total_comparisons": self._chain.get_db_comparison_count(),
            "total_components": self._chain.get_component_count(),
            "total_chains": len(chains),
            "longest_chain_depth": max((len(c) for c in chains), default=0),
            "top_nodes_count": len(self._chain.get_top_nodes()),
            "bottom_nodes_count": len(self._chain.get_bottom_nodes()),
            "built_at": built_at.isoformat() if built_at is not None else None,
        }

    def are_in_same_path(self, img1: str, img2: str) -> bool:
        if (
            img1 not in self._chain.get_all_filenames()
            or img2 not in self._chain.get_all_filenames()
        ):
            return False
        if self._chain.can_reach(img1, img2):
            return True
        if self._chain.can_reach(img2, img1):
            return True
        return False

    # -- Repository facade (#47): the single DB-facing surface ----------

    def add_image(
        self,
        filename: str,
        score: float,
        comparison_count: int,
        prompt_tags: str | None,
        rating_mu: float,
        rating_sigma: float,
    ) -> bool:
        assert self._image_repo is not None
        return self._image_repo.add_image(
            filename=filename,
            score=score,
            comparison_count=comparison_count,
            prompt_tags=prompt_tags,
            rating_mu=rating_mu,
            rating_sigma=rating_sigma,
        )

    def update_image_rating_state(
        self,
        filename: str,
        score: float,
        rating_mu: float,
        rating_sigma: float,
        comparison_count: int,
        touch_timestamp: bool,
    ) -> bool:
        assert self._image_repo is not None
        return self._image_repo.update_image_rating_state(
            filename=filename,
            score=score,
            rating_mu=rating_mu,
            rating_sigma=rating_sigma,
            comparison_count=comparison_count,
            touch_timestamp=touch_timestamp,
        )

    def update_image_tags(self, filename: str, prompt_tags: str) -> None:
        assert self._image_repo is not None
        self._image_repo.update_image_tags(filename, prompt_tags)

    def clear_all_images(self) -> None:
        assert self._image_repo is not None
        self._image_repo.clear_all_images()

    def reset_all_image_ratings(self, score: float) -> Any:
        assert self._image_repo is not None
        return self._image_repo.reset_all_image_ratings(score)

    def get_nodes_with_only_wins(self) -> list[str]:
        assert self._comparison_repo is not None
        return self._comparison_repo.get_nodes_with_only_wins()

    def get_nodes_with_only_losses(self) -> list[str]:
        assert self._comparison_repo is not None
        return self._comparison_repo.get_nodes_with_only_losses()

    def comparison_exists_for_pair(self, filename_a: str, filename_b: str) -> bool:
        assert self._comparison_repo is not None
        return self._comparison_repo.comparison_exists_for_pair(filename_a, filename_b)

    def add_historical_comparison(
        self,
        filename_a: str,
        filename_b: str,
        winner: str,
        timestamp: str,
    ) -> Any:
        assert self._comparison_repo is not None
        return self._comparison_repo.add_historical_comparison(
            filename_a=filename_a,
            filename_b=filename_b,
            winner=winner,
            timestamp=timestamp,
        )

    def clean_comparisons(self) -> Any:
        assert self._comparison_repo is not None
        return self._comparison_repo.clean_comparisons()

    def clear_all_comparisons(self) -> None:
        assert self._comparison_repo is not None
        self._comparison_repo.clear_all_comparisons()
        self._chain.build([], all_filenames=set())
        self._images.clear()
        self._chain.set_db_comparison_count(0)
        self._chain.clear_comparison_history()
        self._loaded = False

    def get_chains_map(self) -> dict[int, ChainDict]:
        if self._chain_map is not None:
            return self._chain_map
        if self._creating_chain_map:
            time.sleep(1)
            return self.get_chains_map()
        self._creating_chain_map = True

        min_chains: dict[int, list[str]] = self._chain.get_chains()

        # Group chains by length
        chain_map: dict[int, list[tuple[int, list[str]]]] = {}
        i: int
        chain: list[str]

        for i, chain in min_chains.items():
            length: int = len(chain)
            if length not in chain_map:
                chain_map[length] = []
            chain_map[length].append((i, chain))

        # Build main chains mapping
        all_nodes: list[NodeProxy] = self.get_all_nodes()
        main_chains: dict[int, list[str]] = {}
        node: NodeProxy
        main: tuple[int, list[str]] | None
        chain_id: int
        for node in all_nodes:
            main = self._chain.get_node_main_chain(node.filename)
            if main is not None:
                chain_id = main[0]
                if chain_id not in main_chains:
                    main_chains[chain_id] = []
                main_chains[chain_id].append(node.filename)

        # Build final map
        final_map: dict[int, ChainDict] = {}
        errors: list[int] = []
        chain_list: list[tuple[int, list[str]]]
        local_main_chains: list[str]
        chain_proxy: ChainProxy
        final_chain: list[NodeTuple]
        node_name: str
        is_main_node: bool
        node_proxy: NodeProxy
        with tqdm(
            chain_map.items(),
            desc="Building final chain map",
            total=len(chain_map),
            unit="chain lengths",
            delay=3.0,
        ) as pbar:
            for length, chain_list in pbar:
                final_map[length] = {}
                for chain_id, chain_nodes in chain_list:
                    if chain_id not in main_chains:
                        errors.append(chain_id)
                        continue

                    local_main_chains = main_chains[chain_id]
                    chain_proxy = self._make_chain(chain_id, chain_nodes)

                    final_chain = []
                    for node_name in chain_nodes:
                        is_main_node = node_name in local_main_chains
                        node_proxy = self._make_node(node_name)
                        final_chain.append((node_proxy, is_main_node))

                    final_map[length][chain_id] = (chain_proxy, final_chain)

        self._chain_map = final_map
        if len(errors) > 0:
            logger.warning(
                f"Chain mapping completed with {len(errors)} non real main chains"
                # f": {errors}"
            )
        self._creating_chain_map = False

        return self._chain_map
