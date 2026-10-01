from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chain_manager import ChainManager
    from .component_proxy import ComponentProxy
    from .node_proxy import NodeProxy

from . import component_proxy as _component_proxy
from . import node_proxy as _node_proxy


class ChainProxy:
    """Represents one directed path (chain). Created from min chain cover results."""

    def __init__(
        self, chain: ChainManager, chain_id: int, node_list: list[str]
    ) -> None:
        self._chain: ChainManager = chain
        self._id: int = chain_id
        self._nodes: list[str] = node_list

    @property
    def id(self) -> int:
        return self._id

    @property
    def nodes(self) -> list[NodeProxy]:
        return [_node_proxy.NodeProxy(self._chain, n) for n in self._nodes]

    @property
    def length(self) -> int:
        return len(self._nodes)

    @property
    def is_main(self) -> bool:
        for node_id in self._nodes:
            main: tuple[int, list[str]] | None = self._chain.get_node_main_chain(
                node_id
            )
            if main is not None and main[0] == self._id:
                return True
        return False

    @property
    def first(self) -> NodeProxy | None:
        if not self._nodes:
            return None
        return _node_proxy.NodeProxy(self._chain, self._nodes[0])

    @property
    def last(self) -> NodeProxy | None:
        if not self._nodes:
            return None
        return _node_proxy.NodeProxy(self._chain, self._nodes[-1])

    def get_component(self) -> ComponentProxy | None:
        if not self._nodes:
            return None
        comp_id: int | None = self._chain.get_component_id(self._nodes[0])
        if comp_id is None:
            return None
        return _component_proxy.ComponentProxy(self._chain, comp_id)

    def __repr__(self) -> str:
        return f"ChainProxy(id={self._id}, length={self.length})"


# Removed as unreferenced anywhere in the module; restore from these descriptions:
#   get_nodes(only_top, only_bottom) -> list of NodeProxy for this chain's nodes,
#     raising ValueError when both flags are True. The unfiltered case duplicates
#     the `nodes` property; the filters select on NodeProxy.is_top/is_bottom.
#   node_position(node_id) -> self._nodes.index(node_id)