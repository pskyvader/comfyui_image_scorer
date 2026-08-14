"""Image processor - discovery, initialization, and rebuild flow."""

from __future__ import annotations

import json
import os
import shutil
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from tqdm import tqdm

from ...core.observability.logger import get_logger, ModuleLogger
from ...core.configuration.settings import config
from ...core.io.serialization import collect_valid_files, discover_files
from ...core.utilities.concurrency import parallel_for
from ...core.filesystem.paths import image_root_processed, output_dir
from ...domain.analysis.trueskill import (
    INITIAL_MEAN,
    INITIAL_UNCERTAINTY,
    public_score_from_rating,
    replay_ratings,
)
from ...domain.database.ports import ComparisonRepository, ImageRepository
from ...domain.comparison.algorithm.phase_order import reset_skip
from .graph_service import CrystalGraph

logger: ModuleLogger = get_logger(__name__)


@dataclass
class PathOps:
    """Infrastructure file/path operations injected by the composition root."""

    ranked_root: Callable[[], Path]
    compute_path: Callable[[str, float], Path]
    sync_metadata: Callable[..., bool]
    clear_folder_cache: Callable[[], None]
    prewarm_folder_cache: Callable[[Path], None]
    deduplicate_scored: Callable[[Path | None, bool, int], int]
    cleanup_orphans: Callable[[Path | None, bool, bool], int]


class ImageProcessor:
    """Process uninitialized images with parallel workers."""

    def __init__(
        self,
        max_workers: int,
        image_repo: ImageRepository,
        comparison_repo: ComparisonRepository,
        graph: CrystalGraph,
        path_ops: PathOps,
    ) -> None:
        ranking_conf = config["ranking"]
        self.max_workers = max_workers
        self.batch_size = int(ranking_conf["batch_size"])
        self.default_score = float(ranking_conf["default_score"])
        self.reserve_count = int(ranking_conf["reserve_count"])

        self._image_repo = image_repo
        self._comparison_repo = comparison_repo
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

    def _extract_prompt_tags(self, data: dict[str, Any]) -> str | None:
        if "positive_prompt" in data:
            prompt = data["positive_prompt"]
            if isinstance(prompt, str) and prompt:
                return prompt
        for value in data.values():
            if isinstance(value, dict):
                result = self._extract_prompt_tags(value)
                if result:
                    return result
        return None

    def clean_json_metadata(
        self,
        json_data: dict[str, Any],
        default_score: float,
        filename: str,
    ) -> dict[str, Any]:
        remove_fields = {
            "score",
            "score_modifier",
            "volatility",
            "confidence",
            "image",
            "comparison_count",
            "rating_mu",
            "rating_sigma",
        }

        if not isinstance(json_data, dict) or not json_data:
            base: dict[str, Any] = {}
        else:
            if len(json_data) == 1:
                only_value = next(iter(json_data.values()))
                if isinstance(only_value, dict) and "positive_prompt" in only_value:
                    json_data = only_value
            base = {k: v for k, v in json_data.items() if k not in remove_fields}
            if not base:
                for _, value in json_data.items():
                    if isinstance(value, dict):
                        base = {
                            k: v for k, v in value.items() if k not in remove_fields
                        }
                        break

        base["score"] = round(float(default_score), 3)
        base["rating_mu"] = INITIAL_MEAN
        base["rating_sigma"] = INITIAL_UNCERTAINTY
        base["comparison_count"] = 0
        base["comparison_history"] = []

        if filename:
            base["filename"] = filename

        base["prompt_tags"] = self._extract_prompt_tags(json_data)
        return base

    def process_image_file(
        self, image_path: Path
    ) -> tuple[bool, str, float | None, str | None, bool, str | None]:
        """Process a single raw image file into the ranked tree."""
        filename = image_path.name
        json_path = image_path.with_suffix(".json")

        if not json_path.exists():
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

        with open(json_path, "r", encoding="utf-8") as handle:
            json_data = json.load(handle)

        cleaned_json = self.clean_json_metadata(
            json_data, default_score=self.default_score, filename=filename
        )

        db_entry = self._image_repo.get_image(filename)
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
        with open(tmp_json, "w", encoding="utf-8") as handle:
            json.dump(cleaned_json, handle, indent=2, ensure_ascii=False)
        os.replace(str(tmp_json), str(json_path))

        dest_image = self._path_ops.compute_path(filename, chosen_score)
        dest_image.parent.mkdir(parents=True, exist_ok=True)
        dest_json = dest_image.with_suffix(".json")

        if dest_image.exists() and image_path.exists():
            if image_path.stat().st_size == dest_image.stat().st_size:
                if json_path.exists():
                    shutil.move(str(json_path), str(dest_json))
                image_path.unlink(missing_ok=True)
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
                if not candidate.exists():
                    dest_image = candidate
                    dest_json = candidate.with_suffix(".json")
                    break
                index += 1

        def safe_move(src: Path, dst: Path) -> bool:
            if not src.exists():
                return dst.exists()
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return True

        if not safe_move(image_path, dest_image):
            return (False, "Image move failed", None, None, False, None)
        if json_path.exists() and not safe_move(json_path, dest_json):
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
        all_imgs = self._image_repo.get_all_images()
        with self.processed_lock:
            self.processed_images.clear()
            for img in all_imgs:
                self.processed_images.add(img["filename"])
        logger.info(
            "Synchronized %s processed images from database.",
            len(self.processed_images),
        )

    def get_fast_total_count(self, source_dir: str) -> int:
        source_path = Path(source_dir).resolve()
        count = 0
        exclude_roots = {self._path_ops.ranked_root().resolve(), Path(output_dir).resolve()}

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

    def process_next_batch(self, source_dir: str, batch_size: int) -> dict[str, Any]:
        if self.is_processing:
            return {"status": "skipped", "message": "Already processing"}

        self.is_processing = True
        db_count = self._image_repo.get_image_count()
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

        stats = {"processed": 0, "added": 0, "errors": 0, "failed": []}
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
                        stats["processed"] += 1
                        db_name = dest_name or filename
                        if score is not None and not db_exists:
                            if self._image_repo.add_image(
                                filename=db_name,
                                score=score,
                                comparison_count=0,
                                prompt_tags=prompt_tags,
                                rating_mu=INITIAL_MEAN,
                                rating_sigma=INITIAL_UNCERTAINTY,
                            ):
                                stats["added"] += 1
                                current_global += 1
                                update_desc()
                            else:
                                stats["errors"] += 1
                    elif "Already processed" not in message:
                        stats["errors"] += 1
                        if len(stats["failed"]) < 5:
                            stats["failed"].append(f"{filename}: {message}")
                    pbar.update(1)
                    pbar.set_postfix(file=filename[:15], added=stats["added"])
        self.is_processing = False
        return stats

    def rebuild_database_from_ranked(self) -> None:
        """Rebuild or repair the ranking database from ranked files and companion JSON."""
        ranked_root = self._path_ops.ranked_root()
        if not ranked_root.exists():
            return

        self.reorganize_folder_structure()

        ranked_root = self._path_ops.ranked_root()
        self._path_ops.deduplicate_scored(root=ranked_root, dry_run=False, limit=0)
        self._path_ops.cleanup_orphans(
            root=ranked_root, dry_run=False, delete_enabled=True
        )
        self._comparison_repo.clear_all_comparisons()
        self._image_repo.clear_all_images()

        dir_file_pairs = discover_files(str(ranked_root))

        prepare_conf = config["prepare"]
        all_entries = collect_valid_files(
            dir_file_pairs,
            max_workers=int(prepare_conf["max_workers"]),
            scored_only=False,
        )

        for img_path, entry, _timestamp, _file_id in all_entries:
            cleaned = self.clean_json_metadata(
                entry, default_score=self.default_score, filename=Path(img_path).name
            )
            self._image_repo.add_image(
                filename=Path(img_path).name,
                score=self.default_score,
                comparison_count=0,
                prompt_tags=cleaned.get("prompt_tags"),
                rating_mu=INITIAL_MEAN,
                rating_sigma=INITIAL_UNCERTAINTY,
            )

        valid_filenames = {img["filename"] for img in self._image_repo.get_all_images()}

        with tqdm(
            total=len(all_entries),
            desc="Adding histories from image",
            unit="img",
            delay=3.0,
        ) as pbar:
            for img_path, entry, _timestamp, file_id in all_entries:
                filename = Path(img_path).name

                cleaned = self.clean_json_metadata(
                    entry, default_score=self.default_score, filename=filename
                )
                prompt_tags = cleaned["prompt_tags"] or self._extract_prompt_tags(
                    cleaned
                )
                existing = self._image_repo.get_image(filename)
                if existing and prompt_tags and existing["prompt_tags"] != prompt_tags:
                    self._image_repo.update_image_tags(filename, prompt_tags)

                if filename in valid_filenames:
                    history = entry.get("comparison_history")
                    if isinstance(history, list):
                        for comp in history:
                            other = comp["other"]
                            timestamp = comp["timestamp"]
                            if not other or not timestamp:
                                continue
                            if other not in valid_filenames:
                                continue
                            winner_file = filename if comp["winner"] else other
                            if winner_file not in valid_filenames:
                                continue
                            self._comparison_repo.add_historical_comparison(
                                filename_a=filename,
                                filename_b=other,
                                winner=winner_file,
                                timestamp=str(timestamp),
                                weight=float(comp["weight"]),
                                transitive_depth=int(comp["transitive_depth"]),
                            )

                pbar.update(1)

        self._comparison_repo.clean_comparisons()

        self._recompute_ratings_from_database_history()

        all_comparisons = self._comparison_repo.get_all_comparisons()
        all_images = self._image_repo.get_all_images()

        filename_to_path: dict[str, Path] = {}
        filename_to_entry: dict[str, dict[str, Any]] = {}
        for img_path, _entry, _ts, _fid in all_entries:
            p = Path(img_path)
            filename_to_path[p.name] = p
            filename_to_entry[p.name] = _entry

        filename_to_comparisons: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for comp in all_comparisons:
            filename_to_comparisons[comp["filename_a"]].append(comp)
            filename_to_comparisons[comp["filename_b"]].append(comp)

        filename_to_image_data: dict[str, dict[str, Any]] = {}
        for img in all_images:
            filename_to_image_data[img["filename"]] = img

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
            for img in all_images
        ]
        prepare_conf = config["prepare"]
        logger.debug("sync json data...")
        parallel_for(
            sync_worker,
            sync_args,
            max_workers=int(prepare_conf["max_workers"]),
            batch_size=int(prepare_conf["batch_size"]),
            desc="Syncing JSON metadata",
            unit="img",
        )

        self._path_ops.clear_folder_cache()
        self.sync_processed_images_from_db()

    def _recompute_ratings_from_database_history(self) -> int:
        self._image_repo.reset_all_image_ratings(score=self.default_score)

        replayed = replay_ratings(self._comparison_repo.get_all_comparisons())

        updated = 0
        with tqdm(
            total=len(replayed),
            desc="Updating scores",
            unit="img",
            leave=False,
            delay=3.0,
        ) as pbar:
            for filename, (rating, count) in replayed.items():
                if self._image_repo.update_image_rating_state(
                    filename=filename,
                    score=public_score_from_rating(rating),
                    rating_mu=rating.mu_skill,
                    rating_sigma=rating.sigma_uncertainty,
                    comparison_count=count,
                    touch_timestamp=False,
                ):
                    updated += 1
                pbar.update(1)

        return updated

    def reorganize_folder_structure(self) -> None:
        ranked_root = self._path_ops.ranked_root()
        if not ranked_root.exists():
            return

        logger.info("[SCANNER] Checking folder structure for loose files...")

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
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as handle:
                        meta = json.load(handle)
                    score = float(meta["score"])
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
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(loose_file), str(target_path))
                if json_path.exists():
                    shutil.move(str(json_path), str(target_path.with_suffix(".json")))
                moved_count += 1
                pbar.update(1)

        if moved_count:
            logger.info(
                "[SCANNER] Reorganized %s loose files into subfolders.", moved_count
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
            reset_skip()
