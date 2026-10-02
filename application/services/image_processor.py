"""Image processor - discovery, initialization, and rebuild flow."""

from __future__ import annotations

import os
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from pathlib import Path
from threading import Lock
import time
from typing import cast

from tqdm import tqdm

from ...core.observability.logger import get_logger, ModuleLogger
from ...core.configuration.settings import config, DB_BULK_CHUNK
from ...core.io.serialization import (
    clean_json_metadata,
    CollectedFile,
    collect_valid_files,
    discover_files,
    extract_prompt_tags,
)
from ...core.utilities.concurrency import parallel_for
from ...core.filesystem.paths import image_root_processed, output_dir
from ...domain.analysis.trueskill import (
    INITIAL_MEAN,
    INITIAL_UNCERTAINTY,
    public_score_from_rating,
    replay_ratings,
)
from ...domain.comparison.algorithm.history_collapse import collapse_comparison_history
from ...domain.ports.files import FilePort
from ...domain.ports.repository import (
    ComparisonRow,
    ImageRow,
    ImageRowForInsert,
    RatingStateUpdate,
)
from .graph_service import CrystalGraph

logger: ModuleLogger = get_logger(__name__)


class ImageProcessor:
    """Process uninitialized images with parallel workers."""

    def __init__(
        self,
        max_workers: int,
        graph: CrystalGraph,
        path_ops: FilePort,
    ) -> None:
        ranking_conf = config["ranking"]
        self.max_workers = max_workers
        self.default_score = float(ranking_conf["default_score"])
        self.reserve_count = int(ranking_conf["reserve_count"])

        self._graph = graph
        self._path_ops = path_ops

        self.processed_lock = Lock()
        self.processed_images: set[str] = set()
        self.image_extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
        self.is_processing = False
        self.total_discovered = 0

        self.lru_size = int(ranking_conf["lru_size"])
        self.recent_images: deque[str] = deque(maxlen=self.lru_size)
        self.recent_chains: deque[str] = deque(maxlen=self.lru_size)
        self.recent_lock: Lock = Lock()
        self.sync_processed_images_from_db()

    def _extract_prompt_tags(self, data: dict[str, object]) -> str | None:
        return extract_prompt_tags(data)

    def process_image_file(
        self, image_path: Path
    ) -> tuple[bool, str, float | None, str | None, bool, str | None]:
        """Process a single raw image file into the ranked tree."""
        filename = image_path.name
        json_path = image_path.with_suffix(".json")

        if not self._path_ops.file_exists(str(json_path)):
            with self.processed_lock:
                self.processed_images.add(filename)
            return (
                False,
                f"Skipping {filename}: missing JSON companion",
                None,
                None,
                False,
                None,
            )

        if filename in self.processed_images:
            return (False, "Already processed", None, None, False, None)

        json_data = self._path_ops.read_json(str(json_path))

        cleaned_json = clean_json_metadata(
            json_data,
            default_score=self.default_score,
            filename=filename,
            initial_mu=INITIAL_MEAN,
            initial_sigma=INITIAL_UNCERTAINTY,
        )

        node = self._graph.get_node(filename)
        db_entry = node.data if node is not None else None
        if db_entry:
            chosen_score = float(db_entry["score"])
            cleaned_json["score"] = round(chosen_score, 3)
            cleaned_json["rating_mu"] = float(db_entry["rating_mu"])
            cleaned_json["rating_sigma"] = float(db_entry["rating_sigma"])
            cleaned_json["comparison_count"] = int(db_entry["comparison_count"])
        else:
            chosen_score = self.default_score
            cleaned_json["score"] = round(chosen_score, 3)
            cleaned_json["rating_mu"] = INITIAL_MEAN
            cleaned_json["rating_sigma"] = INITIAL_UNCERTAINTY
            cleaned_json["comparison_count"] = 0

        tmp_json = json_path.parent / f"{json_path.name}.tmp"
        self._path_ops.write_json(str(tmp_json), cleaned_json)
        self._path_ops.move_file(tmp_json, json_path)

        dest_image = self._path_ops.compute_path(filename, chosen_score)
        self._path_ops.make_directory(str(dest_image.parent))
        dest_json = dest_image.with_suffix(".json")

        if self._path_ops.file_exists(str(dest_image)) and self._path_ops.file_exists(
            str(image_path)
        ):
            if image_path.stat().st_size == dest_image.stat().st_size:
                if self._path_ops.file_exists(str(json_path)):
                    self._path_ops.move_file(json_path, dest_json)
                self._path_ops.remove_file(image_path)
                with self.processed_lock:
                    self.processed_images.add(dest_image.name)
                return (
                    True,
                    f"Duplicate associated with existing file: {dest_image.name}",
                    chosen_score,
                    dest_image.name,
                    bool(db_entry),
                    cleaned_json["prompt_tags"],
                )

            stem = dest_image.stem
            suffix = dest_image.suffix
            index = 1
            while True:
                candidate = dest_image.parent / f"{stem}_{index}{suffix}"
                if not self._path_ops.file_exists(str(candidate)):
                    dest_image = candidate
                    dest_json = candidate.with_suffix(".json")
                    break
                index += 1

        def safe_move(src: Path, dst: Path) -> bool:
            return self._path_ops.move_file(src, dst)

        if not safe_move(image_path, dest_image):
            return (False, "Image move failed", None, None, False, None)
        if self._path_ops.file_exists(str(json_path)) and not safe_move(
            json_path, dest_json
        ):
            return (False, "JSON move failed", None, None, False, None)

        with self.processed_lock:
            self.processed_images.add(dest_image.name)

        return (
            True,
            f"Processed successfully (score: {chosen_score:.3f})",
            chosen_score,
            dest_image.name,
            bool(db_entry),
            cleaned_json["prompt_tags"],
        )

    def sync_processed_images_from_db(self) -> None:
        _start = time.perf_counter()
        all_imgs = [node.data for node in self._graph.get_all_nodes()]
        with self.processed_lock:
            self.processed_images.clear()
            for img in all_imgs:
                self.processed_images.add(img["filename"])
        logger.info(
            f"Synchronized {len(self.processed_images)} processed images from database.",
            start_timer=_start,
        )

    def get_fast_total_count(self, source_dir: str) -> int:
        source_path = Path(source_dir).resolve()
        count = 0
        exclude_roots = {
            self._path_ops.ranked_root().resolve(),
            Path(output_dir).resolve(),
        }

        for root, dirs, files in os.walk(source_path):
            root_path = Path(root).resolve()
            if root_path in exclude_roots:
                dirs[:] = []
                continue
            for file in files:
                if any(file.lower().endswith(ext) for ext in self.image_extensions):
                    count += 1
        self.total_discovered = count
        return count

    def process_next_batch(self, source_dir: str, batch_size: int) -> dict[str, object]:
        if self.is_processing:
            return {"status": "skipped", "message": "Already processing", "added": 0}

        self.is_processing = True
        db_count = self._graph.get_node_count()
        total_goal = getattr(self, "total_discovered", 0)

        if self.total_discovered == 0:
            self.get_fast_total_count(source_dir)

        source_path = Path(source_dir).resolve()
        exclude_roots = [
            Path(image_root_processed).resolve(),
            self._path_ops.ranked_root().resolve(),
            Path(output_dir).resolve(),
        ]
        candidates: list[Path] = []
        for root, dirs, files in os.walk(source_path):
            root_path = Path(root).resolve()
            if root_path in exclude_roots:
                dirs[:] = []
                continue
            for file in files:
                if file in self.processed_images:
                    continue
                if any(file.lower().endswith(ext) for ext in self.image_extensions):
                    candidates.append(root_path / file)

        if not candidates:
            self.is_processing = False
            return {"status": "complete", "added": 0}

        candidates.sort(key=lambda path: os.path.getmtime(path), reverse=True)
        if len(candidates) < self.reserve_count:
            self.is_processing = False
            return {"status": "complete", "added": 0, "message": "Images reserved"}

        batch_files = candidates[self.reserve_count : self.reserve_count + batch_size]

        failed: list[str] = []
        processed = 0
        added = 0
        errors = 0
        current_global = db_count
        system_total = db_count + total_goal

        with tqdm(
            total=len(batch_files),
            desc="[SCANNER] Initializing...",
            unit="img",
            leave=False,
            delay=3.0,
        ) as pbar:

            def update_desc() -> None:
                pbar.set_description(
                    f"[SCANNER] Global: {current_global}/{system_total}"
                )

            update_desc()
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(self.process_image_file, img_path): img_path
                    for img_path in batch_files
                }
                for future in as_completed(future_to_file):
                    filename = future_to_file[future].name
                    success, message, score, dest_name, db_exists, prompt_tags = (
                        future.result()
                    )
                    if success:
                        processed += 1
                        db_name = dest_name or filename
                        if score is not None and not db_exists:
                            if self._graph.add_image(
                                filename=db_name,
                                score=score,
                                comparison_count=0,
                                prompt_tags=prompt_tags,
                                rating_mu=INITIAL_MEAN,
                                rating_sigma=INITIAL_UNCERTAINTY,
                            ):
                                added += 1
                                current_global += 1
                                update_desc()
                            else:
                                errors += 1
                    elif "Already processed" not in message:
                        errors += 1
                        if len(failed) < 5:
                            failed.append(f"{filename}: {message}")
                    pbar.update(1)
                    pbar.set_postfix(file=filename[:15], added=added)
        self.is_processing = False
        return {
            "processed": processed,
            "added": added,
            "errors": errors,
            "failed": failed,
        }

    def rebuild_database_from_ranked(self) -> None:
        """Rebuild or repair the ranking database from ranked files and companion JSON."""
        _start: float = time.perf_counter()
        ranked_root = self._path_ops.ranked_root()
        if not ranked_root.exists():
            return

        self.reorganize_folder_structure()

        ranked_root: Path = self._path_ops.ranked_root()
        self._path_ops.deduplicate_scored(root=ranked_root)
        self._path_ops.cleanup_orphans(root=ranked_root)
        self._graph.clear_all_comparisons()
        self._graph.clear_all_images()

        dir_file_pairs = discover_files(str(ranked_root))

        prepare_conf = config["prepare"]
        all_entries = collect_valid_files(
            dir_file_pairs,
            max_workers=int(prepare_conf["max_workers"]),
            scored_only=False,
        )
        logger.debug(
            f"collected {len(all_entries)} valid entries from ranked files ",
            start_timer=_start,
        )

        image_rows: list[ImageRowForInsert] = []
        for img_path, entry, _timestamp, _file_id in all_entries:
            cleaned = clean_json_metadata(
                entry,
                default_score=self.default_score,
                filename=Path(img_path).name,
                initial_mu=INITIAL_MEAN,
                initial_sigma=INITIAL_UNCERTAINTY,
            )
            image_rows.append(
                {
                    "filename": Path(img_path).name,
                    "score": self.default_score,
                    "rating_mu": INITIAL_MEAN,
                    "rating_sigma": INITIAL_UNCERTAINTY,
                    "comparison_count": 0,
                    "prompt_tags": cleaned.get("prompt_tags"),
                }
            )
        for chunk_start in tqdm(
            range(0, len(image_rows), DB_BULK_CHUNK),
            desc="Adding images",
            unit="chunk",
            delay=3.0,
            position=0,
        ):
            self._graph.add_images_bulk(
                image_rows[chunk_start : chunk_start + DB_BULK_CHUNK]
            )

        self._graph.rebuild_from_database()

        valid_filenames = {node.filename for node in self._graph.get_all_nodes()}
        logger.debug(
            f"valid filenames: {len(valid_filenames)} images in database",
            start_timer=_start,
        )

        comparison_rows: list[ComparisonRow] = []
        with tqdm(
            total=len(all_entries),
            desc="Adding histories from image",
            unit="img",
            delay=3.0,
            position=0,
        ) as pbar:
            for img_path, entry, _timestamp, _file_id in all_entries:
                filename = Path(img_path).name

                cleaned = clean_json_metadata(
                    entry,
                    default_score=self.default_score,
                    filename=filename,
                    initial_mu=INITIAL_MEAN,
                    initial_sigma=INITIAL_UNCERTAINTY,
                )
                prompt_tags = cleaned["prompt_tags"] or extract_prompt_tags(cleaned)
                existing_node = self._graph.get_node(filename)
                existing = existing_node.data if existing_node is not None else None
                if existing and prompt_tags and existing["prompt_tags"] != prompt_tags:
                    self._graph.update_image_tags(filename, prompt_tags)

                if filename not in valid_filenames:
                    pbar.update(1)
                    continue

                history = entry.get("comparison_history")
                if not isinstance(history, list):
                    pbar.update(1)
                    continue

                for comp in cast(list[dict[str, object]], history):
                    other = str(comp.get("other", ""))
                    timestamp = comp.get("timestamp")
                    if not other or not timestamp:
                        continue
                    if other not in valid_filenames:
                        continue
                    if filename == other:
                        continue
                    winner_file = filename if bool(comp.get("winner")) else other
                    if winner_file not in valid_filenames:
                        continue

                    comparison_rows.append(
                        {
                            "filename_a": filename,
                            "filename_b": other,
                            "winner": winner_file,
                            "timestamp": str(timestamp),
                        }
                    )

                pbar.update(1)
        logger.debug(
            f"collected {len(comparison_rows)} historical comparisons",
            start_timer=_start,
        )
        survivors, counts = collapse_comparison_history(
            comparison_rows,
            valid_filenames,
        )
        for chunk_start in tqdm(
            range(0, len(survivors), DB_BULK_CHUNK),
            desc="Adding survivors to database",
            unit="chunk",
            delay=3.0,
            position=0,
        ):
            self._graph.add_comparisons_bulk(
                survivors[chunk_start : chunk_start + DB_BULK_CHUNK]
            )

        logger.debug(
            f"collapsed {len(comparison_rows)} historical comparisons from ranked files "
            f"into {counts.get('kept', len(survivors))} survivors",
            start_timer=_start,
        )

        self._graph.rebuild_from_database()

        self._recompute_ratings_from_database_history()

        self.sync_database_to_files(all_entries)
        self.sync_processed_images_from_db()
        logger.debug(
            f"Rebuild complete. {self._graph.get_node_count()} images in database.",
            start_timer=_start,
        )

    def sync_ranked_files_from_database(self) -> None:
        """Write database state into ranked companion JSON without touching the database."""
        _start: float = time.perf_counter()
        ranked_root: Path = self._path_ops.ranked_root()
        if not ranked_root.exists():
            return

        prepare_conf = config["prepare"]
        all_entries = collect_valid_files(
            discover_files(str(ranked_root)),
            max_workers=int(prepare_conf["max_workers"]),
            scored_only=False,
        )
        self.sync_database_to_files(all_entries)
        logger.debug(
            f"Synced {len(all_entries)} ranked files from database.",
            start_timer=_start,
        )

    def sync_database_to_files(self, all_entries: list[CollectedFile]) -> None:
        """Rewrite each database image's companion JSON from database state."""
        _start: float = time.perf_counter()
        ranked_root: Path = self._path_ops.ranked_root()

        filename_to_path: dict[str, Path] = {}
        filename_to_entry: dict[str, dict[str, object]] = {}
        for img_path, _entry, _ts, _fid in all_entries:
            p = Path(img_path)
            filename_to_path[p.name] = p
            filename_to_entry[p.name] = _entry

        filename_to_image_data: dict[str, ImageRow] = {}
        for node in self._graph.get_all_nodes():
            filename_to_image_data[node.data["filename"]] = node.data

        filename_to_comparisons: dict[str, list[ComparisonRow]] = defaultdict(list)
        for link in self._graph.get_all_links():
            row = link.data
            filename_to_comparisons[str(row["filename_a"])].append(row)
            filename_to_comparisons[str(row["filename_b"])].append(row)

        self._path_ops.prewarm_folder_cache(ranked_root)

        sync_worker = partial(
            self._path_ops.sync_metadata,
            filename_to_path=filename_to_path,
            filename_to_comparisons=filename_to_comparisons,
            filename_to_image_data=filename_to_image_data,
            filename_to_entry=filename_to_entry,
        )
        sync_args = [
            (
                img["filename"],
                float(img["score"]),
                float(img["rating_mu"]),
                float(img["rating_sigma"]),
                int(img["comparison_count"]),
            )
            for img in filename_to_image_data.values()
        ]
        prepare_conf = config["prepare"]
        logger.debug("sync json data...", start_timer=_start)
        parallel_for(
            sync_worker,
            sync_args,
            max_workers=int(prepare_conf["max_workers"]),
            batch_size=int(prepare_conf["batch_size"]),
            desc="Syncing JSON metadata",
            unit="img",
        )

        written, skipped = self._path_ops.pop_sync_counters()
        logger.debug(
            f"sync json wrote {written} file(s), skipped {skipped} unchanged",
            start_timer=_start,
        )
        self._path_ops.clear_folder_cache()

    def _recompute_ratings_from_database_history(self) -> int:
        self._graph.reset_all_image_ratings(score=self.default_score)

        # "default" replays in stored link order so a rebuild of unchanged files
        # reproduces the same ratings; a shuffled order makes every run drift.
        replayed = replay_ratings(
            [link.data for link in self._graph.get_all_links()], order="default"
        )

        rating_updates: list[RatingStateUpdate] = [
            (
                filename,
                public_score_from_rating(rating),
                rating.mu_skill,
                rating.sigma_uncertainty,
                count,
            )
            for filename, (rating, count) in replayed.items()
        ]
        updated = 0
        for chunk_start in tqdm(
            range(0, len(rating_updates), DB_BULK_CHUNK),
            desc="Updating scores",
            unit="chunk",
            leave=False,
            delay=3.0,
        ):
            updated += self._graph.update_image_rating_states_bulk(
                rating_updates[chunk_start : chunk_start + DB_BULK_CHUNK]
            )

        return updated

    def reorganize_folder_structure(self) -> None:
        _start = time.perf_counter()
        ranked_root = self._path_ops.ranked_root()
        if not ranked_root.exists():
            return

        logger.info(
            "[SCANNER] Checking folder structure for loose files...",
            start_timer=_start,
        )

        moves: list[tuple[Path, Path]] = []
        for tier_folder in ranked_root.glob("scored_*"):
            if not tier_folder.is_dir():
                continue
            items = os.listdir(tier_folder)
            has_subfolders = any(
                item.startswith("scored_") and (tier_folder / item).is_dir()
                for item in items
            )
            if not has_subfolders:
                continue
            for item in items:
                loose_file = tier_folder / item
                if (
                    not loose_file.is_file()
                    or loose_file.suffix.lower() not in self.image_extensions
                ):
                    continue
                json_path = loose_file.with_suffix(".json")
                score = self.default_score
                if self._path_ops.file_exists(str(json_path)):
                    meta = self._path_ops.read_json(str(json_path))
                    raw_score = meta.get("score")
                    if isinstance(raw_score, (int, float)):
                        score = float(raw_score)
                target_path = self._path_ops.compute_path(loose_file.name, score)
                if target_path == loose_file:
                    continue
                moves.append((loose_file, target_path))

        moved_count = 0
        with tqdm(
            total=len(moves),
            desc="[SCANNER] Reorganizing files",
            unit="file",
            leave=False,
            delay=3.0,
        ) as pbar:
            for loose_file, target_path in moves:
                json_path = loose_file.with_suffix(".json")
                self._path_ops.make_directory(str(target_path.parent))
                self._path_ops.move_file(loose_file, target_path)
                if self._path_ops.file_exists(str(json_path)):
                    self._path_ops.move_file(
                        json_path, target_path.with_suffix(".json")
                    )
                moved_count += 1
                pbar.update(1)

        if moved_count:
            logger.info(
                f"[SCANNER] Reorganized {moved_count} loose files into subfolders.",
                start_timer=_start,
            )

    def clear_old_cache(self, force: bool) -> None:
        should_clear: bool = (
            force
            or len(self.recent_images) >= self.lru_size
            or len(self.recent_chains) >= self.lru_size
        )
        if force:
            self.recent_images.clear()
            self.recent_chains.clear()
        elif should_clear:
            num_to_remove = int(self.lru_size * 0.75)
            logger.info(
                f"LRU cache full (nodes: {len(self.recent_images)}, chains: {len(self.recent_chains)}). "
                f"Removing {num_to_remove} least recently used items."
            )
            for _ in range(min(len(self.recent_images), num_to_remove)):
                self.recent_images.popleft()
            for _ in range(min(len(self.recent_chains), num_to_remove)):
                self.recent_chains.popleft()

        if should_clear:
            self._graph.rebuild_from_database()
            self._graph.reset_selection_state()
            self._graph.invalidate_images_snapshot()
