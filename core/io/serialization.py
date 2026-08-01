import json
import jsonlines
import os
from pathlib import Path
from typing import Any, Iterator
from tqdm import tqdm
import time

from concurrent.futures import ThreadPoolExecutor, as_completed
from ..observability.logger import get_logger, ModuleLogger
logger: ModuleLogger = get_logger(__name__)


def load_single_jsonl(filename: str, skip_invalid: bool = True) -> Iterator[Any]:
    if not os.path.exists(filename):
        return

    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            stripped: str = line.strip()
            if not stripped:
                continue
            if skip_invalid:
                yield json.loads(stripped)
            else:
                yield json.loads(stripped)


def write_single_jsonl(filename: str, data: list[Any], mode: str) -> None:
    file_path = Path(filename)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if not mode.startswith("r"):
        with tqdm(total=len(data), delay=3.0) as pbar:
            with jsonlines.open(file_path, mode="w") as writer:
                for item in data:
                    writer.write(item)
                    pbar.update(1)



def discover_files(root: str) -> Iterator[tuple[str, str]]:
    _start = time.perf_counter()
    total_files = 0
    for dirpath, _, files in os.walk(root):
        file_set = set(files)
        total_files += len(files)
        for f in files:
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                base = f.rsplit(".", 1)[0]
                json_name = base + ".json"

                if json_name in file_set:
                    yield (
                        os.path.join(dirpath, f),
                        os.path.join(dirpath, json_name),
                    )


def collect_single_file(
    file: tuple[str, str]
) -> tuple[str, dict[str, Any], str, str] | None:
    _start = time.perf_counter()
    img_path, meta_path = file

    file_id = os.path.basename(img_path)
    entry, err = load_json(meta_path, expect=dict)
    if err or entry is None:
        result = None
    else:
        if "score" not in entry:
            keys = list(entry.keys())
            if keys:
                first_key = keys[0]
                if isinstance(entry[first_key], dict) and len(keys) < 5:
                    timestamp = first_key
                    entry = entry[first_key]
                else:
                    timestamp = "unknown"
            else:
                timestamp = "unknown"
        else:
            timestamp = next(iter(entry.keys())) if entry.keys() else "unknown"

        result = (img_path, entry, timestamp, file_id)

    return result


def collect_valid_files(
    files: Iterator[tuple[str, str]],
    max_workers: int,
    scored_only: bool,
) -> list[tuple[str, dict[str, Any], str, str]]:
    collected_data: list[tuple[str, dict[str, Any], str, str]] = []

    if files:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(collect_single_file, file) for file in files
            ]
            # total=len(files)
            with tqdm(desc="Collecting", unit=" files", delay=3.0) as pbar:
                for future in as_completed(futures):
                    result = future.result()

                    pbar.update(1)
                    if result is None:
                        continue
                    if scored_only and ("score" not in result[1]):
                        continue

                    collected_data.append(result)

    return collected_data


def _recursive_parse_json(obj: Any, path: str | None) -> Any:
    _start = time.perf_counter()
    result: Any
    if isinstance(obj, dict):
        result = {k: _recursive_parse_json(v, path) for k, v in obj.items()}
    elif isinstance(obj, list):
        result = [_recursive_parse_json(v, path) for v in obj]
    elif isinstance(obj, str):
        s = obj.strip()
        if (s.startswith("{") and s.endswith("}")) or (
            s.startswith("[") and s.endswith("]")
        ):
            parsed = json.loads(obj)
            if isinstance(parsed, (dict, list)):
                result = _recursive_parse_json(parsed, path)
            else:
                result = parsed
        else:
            result = obj
    else:
        result = obj
    # if isinstance(result, (dict, list)):

    # else:

    return result


def load_json(
    path: str,
    expect: type | tuple[type, ...] | None,
) -> tuple[Any, str | None]:
    _start = time.perf_counter()
    result: tuple[Any, str | None]
    if not path:
        result = (None, "missing_path")
    elif not Path(path).exists():
        result = (None, "not_found")
    else:
        with Path(path).open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            data = _recursive_parse_json(data, path)
        if expect is not None and not isinstance(data, expect):
            result = (None, "invalid_type")
        else:
            result = (data, None)

    return result


def atomic_write_json(path: str, data: Any, *, indent: int | None) -> None:
    _start = time.perf_counter()
    p: Path = Path(path)
    # logger.debug(f"saving: {path}")
    p.parent.mkdir(parents=True, exist_ok=True)

    tmp: Path = p.with_suffix(p.suffix + ".tmp")

    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=indent)

    os.replace(tmp, p)


def load_single_entry_mapping(
    path: str,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    _start = time.perf_counter()
    data, err = load_json(path, expect=dict)
    result: tuple[dict[str, Any] | None, str | None, str | None]
    if err:
        result = (None, None, err)
    elif data is None or len(data.keys()) != 1:
        result = (None, None, "invalid_keys")
    else:
        key = next(iter(data.keys()))
        payload = data[key]
        if not isinstance(payload, dict):
            result = (None, None, "invalid_payload")
        else:
            result = (payload, str(key), None)
    return result
