"""In-memory key/value cache with optional per-instance TTL and size bound."""

import time
from collections import OrderedDict
from collections.abc import Sized

from ...domain.ports.cache import CacheProvider


def _value_size(value: object) -> int:
    """Size a cached value for the byte budget.

    Callers store heterogeneous values (bytes, lists, tuples, dataclasses).
    Only sized values can be measured, so anything else contributes nothing
    rather than raising or counting a container arity as bytes.
    """
    return len(value) if isinstance(value, Sized) else 0


class InMemoryCache(CacheProvider):
    def __init__(
        self,
        default_ttl: float | None = None,
        max_bytes: int | None = None,
    ) -> None:
        self._default_ttl = default_ttl
        self._max_bytes = max_bytes
        self._data: OrderedDict[str, tuple[object, float | None]] = OrderedDict()
        self._size_bytes = 0

    def get(self, key: str) -> object | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        self._data.move_to_end(key)
        value, expires_at = entry
        if expires_at is not None and time.time() >= expires_at:
            self.invalidate(key)
            return None
        return value

    def set(self, key: str, value: object) -> None:
        if key in self._data:
            old_value, _ = self._data[key]
            self._size_bytes -= _value_size(old_value)
            del self._data[key]
        expires_at = (
            time.time() + self._default_ttl if self._default_ttl is not None else None
        )
        self._data[key] = (value, expires_at)
        self._size_bytes += _value_size(value)
        while self._max_bytes is not None and self._size_bytes > self._max_bytes and self._data:
            _, (evicted, _) = self._data.popitem(last=False)
            self._size_bytes -= _value_size(evicted)

    def invalidate(self, key: str) -> None:
        entry = self._data.pop(key, None)
        if entry is not None:
            self._size_bytes -= _value_size(entry[0])

    def clear(self) -> None:
        self._data.clear()
        self._size_bytes = 0
