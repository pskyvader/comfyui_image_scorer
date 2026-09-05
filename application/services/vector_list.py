"""Vector listing helpers over the split/full vector files."""
from typing import Iterator, Any, Union, TypedDict, cast
import numpy as np
import numpy.typing as npt
from tqdm import tqdm
import os
import time

from ...core.observability.logger import get_logger, ModuleLogger
from ...core.configuration.settings import config
from ...domain.vectors.image_vector import ImageVector
from ...domain.vectors.map_vector import MapVector
from ...domain.vectors.number_vector import IntVector, FloatVector
from ...domain.vectors.embedding_vector import EmbeddingVector
from ...domain.vectors.position_vector import PositionVector
from ...domain.vectors.keypoint_vector import KeypointVector
from ...domain.vectors.person_map_vector import PersonMapVector

from ...core.filesystem.paths import split_dir
from ...core.io.serialization import load_single_jsonl, write_single_jsonl
from ...domain.loading import BatchSizerFactory, MapsProvider, ModelLoader
from ...domain.ports.cache import CacheProvider

logger: ModuleLogger = get_logger(__name__)


VectorType = Union[
    MapVector,
    IntVector,
    FloatVector,
    EmbeddingVector,
    ImageVector,
    PositionVector,
    KeypointVector,
    PersonMapVector,
]

class VectorConfig(TypedDict):
    vector: VectorType
    type: str
    name: str
    slot_size: int
    alias: list[str] | None
    max_normalization: int | float
    model_key: str


class VectorList:
    _IMAGE = "image"
    _INT = "int"
    _FLOAT = "float"
    _MAP = "map"
    _EMBEDDING = "embedding"
    _POSITION = "position"
    _KEYPOINT = "keypoint"
    _PERSON_MAP = "person_map"

    def __init__(
        self,
        raw_data: list[tuple[str, dict[str, Any], str, str]],
        read_only: bool,
        model_loader: ModelLoader,
        batch_sizer_factory: BatchSizerFactory,
        maps_provider: MapsProvider,
        cache: CacheProvider,
    ) -> None:

        self.image_paths: dict[str, str] = {}
        self.entries: dict[str, dict[str, Any]] = {}
        self.unique_ids: list[str] = []
        self.vector_config = config["vector"]["vectors"]
        self.sorted_vectors: dict[str, VectorConfig] = {}
        self.read_only = read_only
        self.add_new_to_map = not self.read_only
        self._model_loader = model_loader
        self._batch_sizer_factory = batch_sizer_factory
        self._maps_provider = maps_provider
        self._cache = cache

        self.configure_sorted_vectors()

        if not self.read_only:
            self.load_split_files()

        duplicated: list[str] = []
        for data in raw_data:
            image_path, entry, _timestamp, file_id = data

            if (
                file_id in self.unique_ids
                or file_id in self.entries
                or file_id in self.image_paths
            ):
                duplicated.append(file_id)
            else:
                self.unique_ids.append(file_id)
            self.entries[file_id] = entry
            if not self.read_only:
                self.image_paths[file_id] = image_path
        if len(duplicated) > 0:
            logger.debug(
                f"Found {len(duplicated)} duplicated file_ids in raw_data entries. Sample duplicates: {duplicated[:5]}"
            )
        self.final_vector: list[list[float]] = []
        self.final_text_data: list[dict[str, Any]] = []

    def configure_sorted_vectors(self) -> None:
        for current_type in self.vector_config:
            v_type = current_type["type"]
            name = current_type["name"]

            if v_type == self._MAP:
                vec = MapVector(name, maps_provider=self._maps_provider)
            elif v_type == self._INT:
                vec = IntVector(name, current_type["max_normalization"])
            elif v_type == self._FLOAT:
                vec = FloatVector(name, current_type["max_normalization"])
            elif v_type == self._EMBEDDING:
                slot_size = current_type["slot_size"]
                vec = EmbeddingVector(
                    name, slot_size=slot_size, model_loader=self._model_loader
                )
            elif v_type == self._IMAGE:
                model_key = current_type["model_key"]
                slot_size = current_type["slot_size"]
                vec = ImageVector(
                    name,
                    model_key=model_key,
                    slot_size=slot_size,
                    model_loader=self._model_loader,
                    batch_sizer_factory=self._batch_sizer_factory,
                )
            elif v_type == self._POSITION:
                vec = PositionVector(name)
            elif v_type == self._KEYPOINT:
                vec = KeypointVector(name)
            elif v_type == self._PERSON_MAP:
                vec = PersonMapVector(name, maps_provider=self._maps_provider)
            else:
                raise ValueError(f"Unknown vector type: {v_type}")

            self.sorted_vectors[name] = VectorConfig(
                vector=vec,
                type=v_type,
                name=name,
                slot_size=current_type.get("slot_size", 0),
                alias=current_type.get("alias"),
                max_normalization=current_type.get("max_normalization", 0),
                model_key=current_type.get("model_key", ""),
            )

    def _exclude_present_entry(self, current_vector: VectorType) -> dict[str, dict[str, Any]]:

        new_entries: dict[str, dict[str, Any]] = {}
        current_list = set(current_vector.vector_list.keys())
        for file_id, entry in list(self.entries.items()):
            if file_id in current_list:
                continue
            new_entries[file_id] = entry

        return new_entries

    def _exclude_present_image_path(
        self, current_vector: ImageVector
    ) -> dict[str, str]:

        new_paths: dict[str, str] = {}
        current_list = set(current_vector.path_list.keys())
        for file_id, entry in self.image_paths.items():
            if file_id in current_list:
                continue
            new_paths[file_id] = entry

        return new_paths

    def create_vectors(self) -> None:
        for v in self.sorted_vectors:
            c = self.sorted_vectors[v]
            alias = c["alias"]
            if c["type"] == self._MAP:
                map_vector = cast(MapVector, c["vector"])
                new_entries = self._exclude_present_entry(map_vector)
                map_vector.parse_value_list(new_entries, self.add_new_to_map, alias)
                map_vector.create_vector_list()
                self.sorted_vectors[v]["vector"] = map_vector
            elif c["type"] == self._INT:
                int_vector = cast(IntVector, c["vector"])
                new_entries = self._exclude_present_entry(int_vector)
                int_vector.parse_value_list(new_entries, alias)
                int_vector.create_vector_list()
                self.sorted_vectors[v]["vector"] = int_vector
            elif c["type"] == self._FLOAT:
                float_vector = cast(FloatVector, c["vector"])
                new_entries = self._exclude_present_entry(float_vector)
                float_vector.parse_value_list(new_entries, alias)
                float_vector.create_vector_list()
                if len(float_vector.vector_list) != len(float_vector.value_list):
                    raise ValueError(
                        f"vector length ({len(float_vector.vector_list)}) mismatch with value length ({len(float_vector.value_list)})"
                    )
                self.sorted_vectors[v]["vector"] = float_vector
            elif c["type"] == self._EMBEDDING:
                embedding_vector = cast(EmbeddingVector, c["vector"])
                new_entries = self._exclude_present_entry(embedding_vector)
                embedding_vector.parse_value_list(new_entries, alias)
                embedding_vector.create_vector_list(batch_size=256)
                embedding_vector.create_text_list(batch_size=256)

                self.sorted_vectors[v]["vector"] = embedding_vector
            elif c["type"] == self._IMAGE:
                image_vector = cast(ImageVector, c["vector"])
                new_image_paths: dict[str, str] = self._exclude_present_image_path(
                    image_vector
                )
                image_vector.create_vector_list_from_paths(new_image_paths)
                self.sorted_vectors[v]["vector"] = image_vector
            elif c["type"] == self._POSITION:
                position_vector = cast(PositionVector, c["vector"])
                new_entries = self._exclude_present_entry(position_vector)
                position_vector.parse_value_list(
                    new_entries, self.add_new_to_map, alias
                )
                position_vector.create_vector_list()
                self.sorted_vectors[v]["vector"] = position_vector
            elif c["type"] == self._KEYPOINT:
                keypoint_vector = cast(KeypointVector, c["vector"])
                new_entries = self._exclude_present_entry(keypoint_vector)
                keypoint_vector.parse_value_list(
                    new_entries, self.add_new_to_map, alias
                )
                keypoint_vector.create_vector_list()
                self.sorted_vectors[v]["vector"] = keypoint_vector
            elif c["type"] == self._PERSON_MAP:
                person_map_vector = cast(PersonMapVector, c["vector"])
                new_entries = self._exclude_present_entry(person_map_vector)
                person_map_vector.parse_value_list(
                    new_entries, self.add_new_to_map, alias
                )
                person_map_vector.create_vector_list()
                self.sorted_vectors[v]["vector"] = person_map_vector

    def validate_and_convert(
        self, data: list[list[float]], name: str, target_size: int
    ) -> npt.NDArray[np.float32]:
        arr = np.array(data, dtype=np.float32)
        if arr.shape[1] != target_size:
            raise ValueError(
                f"Error in '{name}': Row length {arr.shape[1]} "
                f"does not match configured slot_size {target_size}"
            )
        return arr

    def filter_missing_vectors(self) -> None:
        logger.debug("filtering missing vectors...")
        valid_ids: list[str] = self.unique_ids
        error_ids: dict[str, list[str]] = {}

        for v in self.sorted_vectors:
            c = self.sorted_vectors[v]
            current_vector: VectorType = c["vector"]
            vector_ids = set(current_vector.vector_list.keys())
            error_ids[c["name"]] = []
            errors: list[str] = []
            for id in valid_ids:
                if id not in vector_ids:
                    errors.append(id)
            if len(errors) > 0:
                error_ids[c["name"]] = errors

            valid_ids = [id for id in valid_ids if id in vector_ids]

        logger.info(f"valid vectors:{len(valid_ids)}")
        if len(error_ids.items()) > 0:
            logger.debug(
                f"error vectors:{[(id,len(errors)) for id,errors in error_ids.items()]}"
            )
        self.unique_ids = valid_ids

    def join_vectors(self) -> list[list[float]]:
        clean_arrays: list[npt.NDArray[np.float32]] = []
        with tqdm(
            total=len(self.sorted_vectors),
            desc="joining vectors",
            unit="vectors",
            position=1,
            delay=3.0,
        ) as pbar:
            for v in self.sorted_vectors:
                c = self.sorted_vectors[v]
                current_vector: VectorType = c["vector"]
                valid_vectors: list[list[float]] = []
                for id in self.unique_ids:
                    vector = current_vector.vector_list[id]
                    if isinstance(vector[0], int):
                        valid_vectors.append([float(x) for x in vector])
                    else:
                        valid_vectors.append(cast(list[float], vector))

                if len(valid_vectors) != len(self.unique_ids):
                    raise ValueError(
                        f"After validation, vector '{c['name']}' has {len(valid_vectors)} valid entries but expected {len(self.unique_ids)}. This should not happen."
                    )

                converted_vector = self.validate_and_convert(
                    (valid_vectors), c["name"], c["slot_size"]
                )
                clean_arrays.append(converted_vector)
                pbar.update(1)

        logger.info("assembling vectors...")
        self.final_vector = np.column_stack(clean_arrays).tolist()
        return self.final_vector

    def convert_text_list(
        self,
        clean_arrays: dict[str, dict[str, Any]],
        current_list: dict[str, str],
        name: str,
    ) -> dict[str, dict[str, Any]]:

        for id, value in current_list.items():
            if id not in clean_arrays:
                clean_arrays[id] = {}
            clean_arrays[id][name] = value
        return clean_arrays

    def join_text_data(self) -> list[dict[str, Any]]:
        if self.final_text_data:
            return self.final_text_data

        initial_arrays: dict[str, dict[str, Any]] = {}
        with tqdm(
            total=len(self.sorted_vectors),
            desc="joining text data",
            unit=" texts",
            position=1,
            delay=3.0,
        ) as pbar:
            for v in self.sorted_vectors:
                c = self.sorted_vectors[v]
                current_vector: VectorType = c["vector"]
                valid_texts: dict[str, str] = {}
                if c["type"] in [
                    self._MAP,
                    self._INT,
                    self._FLOAT,
                    self._POSITION,
                    self._KEYPOINT,
                    self._PERSON_MAP,
                ]:
                    raw_values = cast(
                        "MapVector | IntVector | FloatVector | PositionVector | KeypointVector | PersonMapVector",
                        current_vector,
                    ).value_list
                    for id in self.unique_ids:
                        val = raw_values[id]
                        if isinstance(val, str):
                            valid_texts[id] = val
                        else:
                            valid_texts[id] = str(val)
                elif c["type"] == self._EMBEDDING:
                    text_values = cast(EmbeddingVector, current_vector).text_list
                    for id in self.unique_ids:
                        valid_texts[id] = text_values[id]
                elif c["type"] == self._IMAGE:
                    continue
                else:
                    raise ValueError(
                        f"Unsupported column type for text data: {c['type']}"
                    )

                initial_arrays = self.convert_text_list(
                    initial_arrays, valid_texts, c["name"]
                )
                pbar.update(1)

        clean_arrays: list[dict[str, Any]] = [
            {key: value} for key, value in initial_arrays.items()
        ]
        self.final_text_data = clean_arrays
        return self.final_text_data

    def update_lists(self) -> None:
        logger.info("updating vector lists...")
        self.vectors_list = [
            {fid: vec} for fid, vec in zip(self.unique_ids, self.final_vector)
        ]
        self.text_list = self.final_text_data

    def load_split_files(self) -> None:
        _start = time.perf_counter()

        invalid_entries: dict[str, list[dict[str, Any]]] = {}
        maps_provider = self._maps_provider
        with tqdm(
            total=len(self.sorted_vectors),
            desc="loading split files",
            unit="vectors",
            position=1,
            delay=3.0,
        ) as pbar:
            for v in self.sorted_vectors:
                c = self.sorted_vectors[v]
                name = c["name"]
                v_type = c["type"]
                current_vector: VectorType = c["vector"]

                split_path = os.path.join(split_dir, v_type, f"{name}.jsonl")
                if not os.path.exists(split_path):
                    logger.warning(f"Split file not found: {split_path}")
                    continue

                raw_vals: dict[str, Any] = {}
                vec_vals: dict[str, list[float]] = {}
                int_vec_vals: dict[str, list[int]] = {}
                invalid: list[dict[str, Any]] = []
                cached_split = self._cache.get(f"split:{name}")
                if cached_split is not None:
                    reader: Iterator[dict[str, Any]] = iter(
                        cast(list[dict[str, Any]], cached_split)
                    )
                else:
                    reader: Iterator[dict[str, Any]] = load_single_jsonl(split_path)

                for obj in reader:
                    if obj["raw"] is not None and len(list(obj["vector"])) > 0:
                        self.unique_ids.append(obj["id"])
                        raw_vals[obj["id"]] = obj["raw"]
                        vector_data = obj["vector"]
                        vec_vals[obj["id"]] = vector_data
                        if v_type == self._INT:
                            int_vec_vals[obj["id"]] = [int(x) for x in vector_data]
                        if v_type in (self._MAP, self._PERSON_MAP):
                            maps_provider.register_value(name, obj["raw"])
                    else:
                        invalid.append(obj)

                if invalid:
                    invalid_entries[name] = invalid

                if v_type == self._INT:
                    int_vector = cast(IntVector, current_vector)
                    int_vector.vector_list = int_vec_vals
                elif v_type == self._IMAGE:
                    cast(ImageVector, current_vector).vector_list = vec_vals
                else:
                    cast(
                        "MapVector | FloatVector | EmbeddingVector | PositionVector | KeypointVector | PersonMapVector",
                        current_vector,
                    ).vector_list = vec_vals

                if v_type in [
                    self._MAP,
                    self._INT,
                    self._FLOAT,
                    self._POSITION,
                    self._KEYPOINT,
                    self._PERSON_MAP,
                ]:
                    cast(
                        "MapVector | IntVector | FloatVector | PositionVector | KeypointVector | PersonMapVector",
                        current_vector,
                    ).value_list = raw_vals
                elif v_type == self._EMBEDDING:
                    cast(EmbeddingVector, current_vector).text_list = raw_vals
                elif v_type == self._IMAGE:
                    cast(ImageVector, current_vector).path_list = raw_vals
                pbar.update(1)

        logger.debug(f"before unique:{len(self.unique_ids)}")
        self.unique_ids = list(set(self.unique_ids))
        logger.debug(f"after unique:{len(self.unique_ids)}")

        if len(invalid_entries.items()) > 0:

            logger.debug(
                f"invalid ids: {[(name,len(value)) for name,value in invalid_entries.items()]}"
            )
            example = list(invalid_entries.items())[0]
            example = list(invalid_entries.items())[0]
            # Avoid nested quote usage in f-strings for Python 3.10 compatibility
            cond = "raw ok" if example[1][0]["raw"] else "raw missing"
            vec_status = "vector ok" if example[1][0]["vector"] else "vector missing"
            logger.debug(
                f"example clip skip: {example}, conditions: {cond} , {vec_status}"
            )

    def export_split_files(self) -> None:
        logger.info("Exporting split data files...")
        with tqdm(
            total=len(self.sorted_vectors),
            desc="exporting splits",
            unit="vectors",
            position=1,
            delay=3.0,
        ) as pbar:
            for v in self.sorted_vectors:
                c = self.sorted_vectors[v]
                name = c["name"]
                v_type = c["type"]
                current_vector: VectorType = c["vector"]
                raw_values: dict[str, Any] = {}

                if v_type in [
                    self._MAP,
                    self._INT,
                    self._FLOAT,
                    self._POSITION,
                    self._KEYPOINT,
                    self._PERSON_MAP,
                ]:
                    raw_values = cast(
                        "MapVector | IntVector | FloatVector | PositionVector | KeypointVector | PersonMapVector",
                        current_vector,
                    ).value_list
                elif v_type == self._EMBEDDING:
                    raw_values = cast(EmbeddingVector, current_vector).text_list
                elif v_type == self._IMAGE:
                    raw_values = {id: id for id in current_vector.vector_list.keys()}
                else:
                    raise ValueError(f"Unknown vector type: {v_type}")

                vector_values_len = len(current_vector.vector_list)
                if vector_values_len != len(raw_values):
                    raise ValueError(
                        f"Length mismatch in vector '{name}' of type '{v_type}'. "
                        f"raw values: {len(raw_values)}, vector values: {vector_values_len}"
                    )

                out_dir = os.path.join(split_dir, v_type)
                os.makedirs(out_dir, exist_ok=True)

                out_file = os.path.join(out_dir, f"{name}.jsonl")

                split_data: list[dict[str, Any]] = []

                for uid in current_vector.vector_list.keys():
                    raw_val = raw_values[uid]
                    vec_val = current_vector.vector_list[uid]
                    split_data.append({"id": uid, "raw": raw_val, "vector": vec_val})

                self._cache.set(f"split:{name}", split_data)
                write_single_jsonl(out_file, split_data, mode="w")
                pbar.update(1)
