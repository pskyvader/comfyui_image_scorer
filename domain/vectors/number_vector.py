from .helpers import get_value_from_entry
from ...core.observability.logger import get_logger, ModuleLogger

logger: ModuleLogger = get_logger(__name__)

error_count: int = 0


def _require_number(value: object, name: str, entry_id: str) -> int | float | str:
    """Narrow a raw entry value to the numeric shapes a numeric vector accepts."""
    if not isinstance(value, int | float | str):
        global error_count
        error_count += 1
        # raise TypeError
        # logger.error(
        #     f"Vector '{name}' for id '{entry_id}' expects a number, "
        #     f"got {type(value).__name__} ({value})"
        #     f"error count {error_count}"
        # )
        return 0
    return value


class IntVector:
    def __init__(self, name: str, max_normalization: int | None) -> None:
        self.name = name
        self.max_normalization = max_normalization
        self.value_list: dict[str, int] = {}
        self.vector_list: dict[str, list[int]] = {}

    def parse_value_list(
        self, entries: dict[str, dict[str, object]], alias: list[str] | None
    ) -> dict[str, int]:
        global error_count
        error_count = 0
        for id, entry in list(entries.items()):
            current_value = _require_number(
                get_value_from_entry(entry, self.name, alias), self.name, id
            )
            self.value_list[id] = int(current_value)
        if error_count > 0:
            logger.warning(
                f"Total errors encountered while parsing '{self.name}': {error_count}"
            )
        return self.value_list

    def create_vector_list(self) -> dict[str, list[int]]:
        for id, current_value in self.value_list.items():
            clamped = (
                min(current_value, self.max_normalization)
                if self.max_normalization is not None
                else current_value
            )
            current_vector: list[int] = [clamped]
            self.vector_list[id] = current_vector
        return self.vector_list


class FloatVector:
    def __init__(self, name: str, max_normalization: float | None) -> None:
        self.name = name
        self.max_normalization = max_normalization
        self.value_list: dict[str, float] = {}
        self.vector_list: dict[str, list[float]] = {}

    def parse_value_list(
        self, entries: dict[str, dict[str, object]], alias: list[str] | None
    ) -> dict[str, float]:
        global error_count
        error_count = 0
        for id, entry in list(entries.items()):
            current_value = _require_number(
                get_value_from_entry(entry, self.name, alias), self.name, id
            )
            self.value_list[id] = float(current_value)
        if error_count > 0:
            logger.warning(
                f"Total errors encountered while parsing '{self.name}': {error_count}"
            )
        return self.value_list

    def create_vector_list(self) -> dict[str, list[float]]:
        for id, current_value in self.value_list.items():
            clamped = (
                min(current_value, self.max_normalization)
                if self.max_normalization is not None
                else current_value
            )
            current_vector: list[float] = [clamped]
            self.vector_list[id] = current_vector
        return self.vector_list
