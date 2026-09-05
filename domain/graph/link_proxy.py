from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chain_manager import ChainManager
    from .node_proxy import NodeProxy

from . import node_proxy as _node_proxy


class _ComparisonRecord:
    """Internal record for a comparison link — not exposed outside the graph subsystem."""

    __slots__ = ("id", "winner", "loser", "timestamp")

    def __init__(self, id: int, winner: str, loser: str, timestamp: str) -> None:
        self.id: int = id
        self.winner: str = winner
        self.loser: str = loser
        self.timestamp: str = timestamp


class LinkProxy:
    """Represents one comparison link between two images. Created on demand, zero overhead."""

    def __init__(
        self,
        chain: ChainManager,
        comparison_record: _ComparisonRecord,
    ) -> None:
        self._chain: ChainManager = chain
        self._record: _ComparisonRecord = comparison_record

    @property
    def id(self) -> int:
        return self._record.id

    @property
    def winner(self) -> str:
        return self._record.winner

    @property
    def loser(self) -> str:
        return self._record.loser

    @property
    def timestamp(self) -> str:
        return self._record.timestamp

    @property
    def data(self) -> dict[str, object]:
        return {
            "id": self.id,
            "filename_a": self.winner,
            "filename_b": self.loser,
            "winner": self.winner,
            "timestamp": self.timestamp,
        }

    @property
    def winner_node(self) -> NodeProxy | None:
        return _node_proxy.NodeProxy(self._chain, self._record.winner)

    @property
    def loser_node(self) -> NodeProxy | None:
        return _node_proxy.NodeProxy(self._chain, self._record.loser)

    def __repr__(self) -> str:
        return f"LinkProxy(id={self._record.id}, winner={self._record.winner}, loser={self._record.loser})"


  # Protocol alias
  # Protocol alias

  # Protocol alias
  # Protocol alias

  # Protocol alias

  # Protocol alias