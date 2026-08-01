from __future__ import annotations

from typing import Any

from ....core.observability.logger import get_logger, ModuleLogger
from ....core.configuration.settings import config
from ....domain.vectors.helpers import get_value_from_entry

logger: ModuleLogger = get_logger(__name__)


def register_map_values(processed_data: list) -> None:
    from ....infrastructure.loading.maps_loader import maps_list

    map_configs = [
        v for v in config["vector"]["vectors"] if v["type"] in ("map", "person_map")
    ]
    if not map_configs:
        return
    for _path, entry, _cat, _extra in processed_data:
        if not isinstance(entry, dict):
            continue
        for v in map_configs:
            name = v["name"]
            alias = v.get("alias")
            value = get_value_from_entry(entry, name, alias)
            if value is None:
                continue
            maps_list.register_value(name, value)
