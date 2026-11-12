from __future__ import annotations
import hashlib
import os
import json
from collections.abc import Callable
from typing import NotRequired, TypedDict

import numpy as np
from numpy import typing as npt
import lightgbm as lgb
from tqdm import tqdm
import gc

from sklearn.preprocessing import PolynomialFeatures

from ...core.observability.logger import get_logger
from ...core.configuration.settings import config, VectorEntry
from ...core.filesystem.paths import maps_dir
from ..analysis.trueskill import (
    public_score_from_rating,
    replay_ratings,
)
from ..ports.loading import ModelTrainingService, TrainingLoader

logger = get_logger(__name__)


class FeatureInfo(TypedDict):
    """Where one scalar feature sits inside its source vector."""

    vector_name: str
    position_in_vector: int
    total_in_vector: int


class VectorRange(TypedDict):
    """Feature index span occupied by one configured vector."""

    start_idx: int
    end_idx: int
    slot_size: int
    type: str
    per_unit_size: NotRequired[int]


class FeatureMapping(TypedDict):
    """Forward and reverse maps over the configured feature layout."""

    feature_to_vector: dict[int, FeatureInfo]
    vector_ranges: dict[str, VectorRange]
    total_features: int


class InteractionStats(TypedDict):
    """Accumulated statistics for the two-pass interaction correlation scan."""

    sum_x: npt.NDArray[np.float64]
    sum_x_sq: npt.NDArray[np.float64]
    sum_xy: npt.NDArray[np.float64]
    sum_y: npt.NDArray[np.float32] | np.float32 | int
    sum_y_sq: npt.NDArray[np.float32] | np.float32 | int
    n: int


def get_feature_mapping_from_config() -> FeatureMapping:
    """
    Creates a mapping from feature indices to vector names and positions.
    Returns both a forward map (index -> vector info) and reverse map (vector -> indices).
    """
    feature_to_vector: dict[int, FeatureInfo] = {}
    vector_ranges: dict[str, VectorRange] = {}
    current_idx = 0
    config_vectors: list[VectorEntry] = config["vector"]["vectors"]
    for vector_config in config_vectors:
        vec_name = vector_config["name"]
        slot_size = vector_config["slot_size"]
        entry: VectorRange = {
            "start_idx": current_idx,
            "end_idx": current_idx + slot_size,
            "slot_size": slot_size,
            "type": vector_config["type"],
        }
        if "per_unit_size" in vector_config:
            entry["per_unit_size"] = vector_config["per_unit_size"]
        vector_ranges[vec_name] = entry

        for i in range(slot_size):
            feature_to_vector[current_idx + i] = {
                "vector_name": vec_name,
                "position_in_vector": i,
                "total_in_vector": slot_size,
            }

        current_idx += slot_size

    return {
        "feature_to_vector": feature_to_vector,
        "vector_ranges": vector_ranges,
        "total_features": current_idx,
    }


class DataTransformer:
    poly = PolynomialFeatures(degree=2, include_bias=False, interaction_only=True)

    def __init__(
        self, training_loader: TrainingLoader, model_trainer: ModelTrainingService
    ) -> None:
        """Data transformer for feature engineering and interaction features.

        Responsible for generating polynomial interaction features, training
        LightGBM models for feature importance ranking, and applying cached
        feature filters to vector representations.

        Dependencies (injected through composition root):
        - ``training_loader``: provides access to vectors, scores, and cached rules
        - ``model_trainer``: provides LightGBM training model utilities
        """
        self.training_loader = training_loader
        self.model_trainer = model_trainer
        feature_mapping = get_feature_mapping_from_config()
        self.feature_to_vector: dict[int, FeatureInfo] = feature_mapping[
            "feature_to_vector"
        ]
        self.vector_ranges: dict[str, VectorRange] = feature_mapping["vector_ranges"]

    def filter_low_comparisons(
        self,
        threshold: int,
    ) -> dict[str, tuple[float, int]]:
        """Return the kept subset as filename -> (score, count).

        Filenames with at least ``threshold`` comparisons are kept, then the
        TrueSkill ratings are replayed using only comparisons between kept
        filenames so the surviving scores are self-consistent for that subset.
        The result is cached in comparison_rule.npz keyed by threshold.
        """
        rule_cached = self.training_loader.load_comparison_rule(threshold)
        if rule_cached is not None:
            return rule_cached

        rows = self.training_loader.load_comparison_rows()

        counts: dict[str, int] = {}
        for row in rows:
            counts[row["filename_a"]] = counts.get(row["filename_a"], 0) + 1
            counts[row["filename_b"]] = counts.get(row["filename_b"], 0) + 1
        kept_filenames = {fid for fid, count in counts.items() if count >= threshold}

        subset_rows = [
            row
            for row in rows
            if row["filename_a"] in kept_filenames
            and row["filename_b"] in kept_filenames
        ]
        replayed = replay_ratings(subset_rows, order="default")
        rule = {
            fid: (public_score_from_rating(rating), count)
            for fid, (rating, count) in replayed.items()
        }

        self.training_loader.save_comparison_rule(threshold, rule)
        return rule

    def filter_unused_features(
        self,
        vectors_keyed: dict[str, npt.NDArray[np.float32]],
        scores_keyed: dict[str, float],
        steps: int,
    ) -> npt.NDArray[np.intp]:
        """
        Trains a fast LightGBM model on the keyed vectors/scores to identify and
        remove features with zero importance and low cumulative gain. Returns
        only the kept column indices (the feature mask). Caches the mask as
        feature_rule.npz alongside the layout width it was built for. No
        sorting or alignment is performed here; the keyed inputs are already
        consistent.

        The filter runs over non-zero-importance features: zero-contribution
        features are always dropped while the filter is enabled, and the
        keep-proportion prune applies to the survivors. Skipping the filter
        entirely is the only way to keep zero-contribution features.
        """
        n_features_in = next(iter(vectors_keyed.values())).shape[0]

        rule_cached = self.training_loader.load_feature_rule(n_features_in)
        if rule_cached is not None:
            return rule_cached

        # Build (x, y) from the keyed inputs without imposing any ordering.
        # order: list[str] = list(scores_keyed.keys())
        # filter out scores for missing vectors
        order: list[str] = [fid for fid in scores_keyed.keys() if fid in vectors_keyed]

        # logger.debug(
        #     f"scores: {len(scores_keyed.keys())}, vectors: {len(vectors_keyed.keys())}, order: {len(order)}"
        # )

        x = np.array([vectors_keyed[fid] for fid in order], dtype=np.float32)
        y = np.array([scores_keyed[fid] for fid in order], dtype=np.float32)

        logger.debug(f"y shape: {y.shape}, x shape: {x.shape}")

        user_verbosity = int(config["training"]["verbosity"])

        # Create training model using shared trainer with minimal config
        config_dict: dict[str, object] = {
            "n_estimators": steps,
        }
        if config["training"]["objective"] == "lambdarank":
            # Feature filtering still uses the scalar score target even when
            # the final training objective is pairwise ranking.
            config_dict["objective"] = "regression"
        self.model_trainer.create_training_model(config_dict)
        model = self.model_trainer.training_model
        assert model is not None

        # Setup callbacks for logging
        callbacks: list[Callable[..., None]] = [
            lgb.log_evaluation(period=-1)
        ]  # suppress default logger
        pbar = None
        if user_verbosity >= 0:
            # Use tqdm progress bar
            pbar = tqdm(total=steps, desc="Training LightGBM", delay=3.0)

            def pbar_callback(_: int) -> None:
                pbar.update(1)

            callbacks.append(pbar_callback)

        # Train the model
        model.fit(x, y, callbacks=callbacks)
        if pbar is not None:
            pbar.close()

        # Get feature importances (gain)
        importances: npt.NDArray[np.float32] = model.feature_importances_
        n_features = len(importances)

        n_zeros = int(np.count_nonzero(importances == 0))
        logger.debug(
            f"Found {n_zeros} features with zero gain out of {n_features} total features."
        )

        # --- Step 1: remove all zero-gain features
        nonzero_mask = importances > 0
        nonzero_importances = importances[nonzero_mask]
        nonzero_indices = np.where(nonzero_mask)[0]

        # --- Step 2: cumulative gain pruning
        sorted_idx = np.argsort(nonzero_importances)[::-1]  # descending
        sorted_importances = nonzero_importances[sorted_idx]
        sorted_indices = nonzero_indices[sorted_idx]

        cumulative = np.cumsum(sorted_importances)
        keep_proportion = float(config["training"]["rule_keep_proportion"])
        keep_mask = np.ones(sorted_indices.shape[0], dtype=bool)
        if cumulative.size:
            cumulative = cumulative / cumulative[-1]  # normalize to 1
            # Keep features until cumulative gain reaches the proportion
            keep_mask = cumulative <= keep_proportion
            # Always keep at least one feature
            if not np.any(keep_mask):
                keep_mask[0] = True
        else:
            # No feature carried any gain, so there is nothing to rank and
            # nothing to prune. Keep them all rather than dropping the model.
            logger.debug(
                f"All {n_features} features had zero gain; keeping every feature."
            )

        kept_indices = sorted_indices[keep_mask]

        # Cache only the mask (kept column indices); the caller applies it.
        self.training_loader.save_feature_rule(kept_indices, n_features_in)
        logger.debug("Saved feature rule to cache")

        return kept_indices

    def calculate_interaction_batch(
        self,
        X_batch: npt.NDArray[np.float32],
        y_batch: npt.NDArray[np.float32],
        n_features_in: int,
        accumulators: InteractionStats,
    ) -> InteractionStats:
        """Compute interaction feature statistics for a batch of data.

        Updates accumulators with sum of interaction terms, sum of squares,
        and dot product with targets. Used in the two-pass correlation
        calculation for selecting top-K interaction features.

        Args:
            X_batch: input feature batch of shape ``(batch_size, n_features_in)``
            y_batch: target values of shape ``(batch_size,)``
            n_features_in: number of original features (before polynomial expansion)
            accumulators: dict with keys ``sum_x``, ``sum_x_sq``, ``sum_xy``,
                ``sum_y``, ``sum_y_sq``, ``n`` that accumulate statistics
                across batches

        Returns:
            Updated accumulators dict with accumulated statistics.
        """
        # Generate Poly
        X_poly_full: npt.NDArray[np.float32] = np.asarray(
            self.poly.fit_transform(X_batch), dtype=np.float32
        )
        # Extract only interactions
        X_inter_batch = X_poly_full[:, n_features_in:]
        # Stats
        accumulators["sum_x"] += np.sum(X_inter_batch, axis=0)
        accumulators["sum_x_sq"] += np.sum(X_inter_batch**2, axis=0)
        accumulators["sum_xy"] += np.dot(X_inter_batch.T, y_batch)

        accumulators["sum_y"] += np.sum(y_batch)
        accumulators["sum_y_sq"] += np.sum(y_batch**2)
        accumulators["n"] += len(X_batch)

        del X_poly_full, X_inter_batch
        gc.collect()
        return accumulators

    def compute_correlations(
        self, k: int, accumulators: InteractionStats
    ) -> npt.NDArray[np.intp]:
        n = accumulators["n"]
        # Compute Correlations (Pearson)
        numerator = (n * accumulators["sum_xy"]) - (
            accumulators["sum_x"] * accumulators["sum_y"]
        )
        denominator_x = (n * accumulators["sum_x_sq"]) - (accumulators["sum_x"] ** 2)
        denominator_y = (n * accumulators["sum_y_sq"]) - (accumulators["sum_y"] ** 2)

        # Avoid div by zero / invalid sqrt
        denominator_x[denominator_x <= 0] = 1e-10
        denominator = np.sqrt(denominator_x * denominator_y)

        correlation = numerator / denominator
        f_scores = (correlation**2) / (1 - correlation**2 + 1e-10) * (n - 2)
        f_scores = np.nan_to_num(f_scores, nan=0.0)

        top_k_indices_local = np.argsort(f_scores)[-k:]
        return np.sort(top_k_indices_local)

    def _scan_interactions(
        self,
        x: npt.NDArray[np.float32],
        y: npt.NDArray[np.float32],
        n_features_in: int,
        n_interactions: int,
        target_k: int,
    ) -> npt.NDArray[np.intp]:
        """Two-pass correlation scan over the raw matrix, returning the local
        indices of the top-K pairwise products (pass 1 stats, pass 2 selection;
        the products themselves are rebuilt on demand from the indices)."""
        n_samples = x.shape[0]
        batch_size = _interaction_batch_size(n_features_in)

        accumulators: InteractionStats = {
            "sum_x": np.zeros(n_interactions),
            "sum_x_sq": np.zeros(n_interactions),
            "sum_xy": np.zeros(n_interactions),
            "sum_y": 0,
            "sum_y_sq": 0,
            "n": 0,
        }

        logger.debug(
            f"Scanning {n_interactions} potential interactions in batches of {batch_size}..."
        )

        with tqdm(
            total=n_samples, desc="Computing Correlations", unit="samples", delay=3.0
        ) as pbar:
            for i in range(0, n_samples, batch_size):
                end_idx = min(i + batch_size, n_samples)
                X_batch = x[i:end_idx]
                y_batch = y[i:end_idx]
                accumulators = self.calculate_interaction_batch(
                    X_batch, y_batch, n_features_in, accumulators
                )
                pbar.update(len(X_batch))

        k = min(target_k, n_interactions)
        return self.compute_correlations(k, accumulators)

    def create_interaction_rule(
        self,
        vectors_keyed: dict[str, npt.NDArray[np.float32]],
        scores_keyed: dict[str, float],
        target_k: int,
    ) -> dict[str, npt.NDArray[np.float32]]:
        """Extend every keyed vector with its selected interaction products.

        Loads the interaction rule for the raw layout width, rebuilding it by a
        two-pass correlation scan over the current data when missing, then
        appends the selected pairwise products to each keyed vector. The rule
        stores only the local interaction-column indices, so extending is
        order-safe regardless of which files exist.
        """
        n_features_in = next(iter(vectors_keyed.values())).shape[0]
        indices = self.training_loader.load_interaction_rule(n_features_in)
        if indices is None:
            n_interactions = (n_features_in * (n_features_in - 1)) // 2
            if n_interactions == 0:
                indices = np.array([], dtype=np.intp)
            else:
                order = [fid for fid in scores_keyed if fid in vectors_keyed]
                x = np.array([vectors_keyed[fid] for fid in order], dtype=np.float32)
                y = np.array([scores_keyed[fid] for fid in order], dtype=np.float32)
                indices = self._scan_interactions(
                    x, y, n_features_in, n_interactions, target_k
                )
            self.training_loader.save_interaction_rule(indices, n_features_in)
            logger.debug("Saved interaction rule to cache")

        extended: dict[str, npt.NDArray[np.float32]] = {}
        fids = list(vectors_keyed)
        batch_size = _interaction_batch_size(n_features_in)
        for i in range(0, len(fids), batch_size):
            chunk = fids[i : i + batch_size]
            applied = self._apply_interaction_rule(
                [vectors_keyed[fid] for fid in chunk], indices
            )
            for fid, row in zip(chunk, applied):
                extended[fid] = row
        return extended

    def apply_feature_filter(
        self, vecs: list[npt.NDArray[np.float32]]
    ) -> list[npt.NDArray[np.float32]]:
        """
        Applies the feature filter (kept_indices) from feature_rule.npz to the
        input vectors, keeping only the rule's columns. The rule must exist and
        match the incoming layout width; prediction-time mismatches raise so a
        stale rule can never silently mis-align a serving vector.
        """

        n_features_in = vecs[0].shape[0]
        kept_indices = self.training_loader.load_feature_rule(n_features_in)
        if kept_indices is None:
            raise FileNotFoundError("Feature rule not found, must generate first")

        return [vec[kept_indices] for vec in vecs]

    def apply_interaction_features(
        self, vecs: list[npt.NDArray[np.float32]]
    ) -> npt.NDArray[np.float32]:
        """
        Appends the interaction products selected by the cached rule to the
        input vectors. The rule must exist and match the incoming layout
        width; prediction-time mismatches raise so a stale rule can never
        silently mis-align a serving vector.
        """
        n_features_in = vecs[0].shape[0]
        interaction_indices = self.training_loader.load_interaction_rule(n_features_in)
        if interaction_indices is None:
            raise FileNotFoundError("Interaction rule not found, must generate first")
        return self._apply_interaction_rule(vecs, interaction_indices)

    def _apply_interaction_rule(
        self,
        vecs: list[npt.NDArray[np.float32]],
        interaction_indices: npt.NDArray[np.intp],
    ) -> npt.NDArray[np.float32]:
        vecs_np = np.array(vecs)  # shape: (batch_size, feature_dim)
        poly_features: npt.NDArray[np.float32] = np.asarray(
            self.poly.fit_transform(vecs_np), dtype=np.float32
        )  # shape: (batch_size, n_poly_features)

        inter_feats = poly_features[:, vecs_np.shape[1] :][:, interaction_indices]

        # Concatenate original features and selected interaction features
        return np.hstack([vecs_np, inter_feats])


def _interaction_batch_size(n_features_in: int) -> int:
    """Row batch size that keeps one full-width interaction matrix near 8 GB."""
    n_interactions = (n_features_in * (n_features_in - 1)) // 2
    bytes_per_row = (n_features_in + n_interactions) * 8
    return min(5000, max(1, int(8 * 1024**3 / bytes_per_row)))


def rule_fingerprint(
    interaction_digest: bytes | None, feature_digest: bytes | None
) -> int | None:
    """Compose both rule digests into a single fingerprint of the data layout.

    ``None`` when neither rule exists, matching a model trained without
    transforms. Both digests are hashed in a fixed order so the fingerprint
    changes whenever either rule's kept indices change.
    """
    if interaction_digest is None and feature_digest is None:
        return None
    h = hashlib.blake2b(digest_size=16)
    h.update(interaction_digest or b"")
    h.update(feature_digest or b"")
    return int.from_bytes(h.digest(), "big")


def _label_position_slot(pos_in_unit: int) -> str:
    """Return a position slot label by index.

    Args:
        pos_in_unit: index of the position slot (0-4 for x,y,width,height,confidence;
                     higher values use ``slot_N`` naming)

    Returns:
        ``"x"``, ``"y"``, ``"width"``, ``"height"``, ``"confidence"``, or
        ``"slot_N```` for indices beyond 4.
    """
    return (
        ["x", "y", "width", "height", "confidence"][pos_in_unit]
        if pos_in_unit < 5
        else f"slot_{pos_in_unit}"
    )


def _label_keypoint_slot(vec_name: str, pos_in_unit: int) -> str:
    """Return a keypoint slot label by vector name and index.

    Args:
        vec_name: name of the vector (e.g. ``"keypoint"``)
        pos_in_unit: index of the keypoint slot (0-3 for x,y,z,visibility;
                     higher values use ``slot_N`` naming)

    Returns:
        ``"vec_name_x"``, ``"vec_name_y"``, ``"vec_name_z"``, ``"vec_name_visibility"``,
        or ``"vec_name_slot_N"`` for indices beyond 3.
    """
    coord = (
        ["x", "y", "z", "visibility"][pos_in_unit]
        if pos_in_unit < 4
        else f"slot_{pos_in_unit}"
    )
    return f"{vec_name}_{coord}"


def _label_person_map_slot(vec_name: str, pos_in_unit: int) -> str:
    """Return a person-map slot label by vector name and index.

    Uses the map JSON to look up category labels for person-map vectors.

    Args:
        vec_name: name of the person-map vector
        pos_in_unit: index of the slot position

    Returns:
        Category label string at the given index, or ``"slot_N```` if the
        index is out of range or no map JSON is found.
    """
    labels = _load_map_slots(vec_name)
    if labels and pos_in_unit < len(labels):
        return labels[pos_in_unit]
    return f"slot_{pos_in_unit}"


def _load_map_slots(vec_name: str) -> list[str] | None:
    """Load the saved map JSON for a map-type vector, returning slot labels by index."""
    path = os.path.join(maps_dir, f"{vec_name}_map.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _print_vector_summary(
    vec_name: str,
    vec_type: str,
    kept_in_vec: list[int],
    total_in_vec: int,
    slot_size: int,
    per_unit_size: int | None,
    start_idx: int,
) -> None:
    """Print one vector line (or expanded lines for known multi-slot / map vectors)."""
    kept_count = len(kept_in_vec)
    pct = 100.0 * kept_count / total_in_vec if total_in_vec else 0

    if per_unit_size and per_unit_size > 1:
        # Multi-slot vector (position / keypoint / person_map) broken down per unit
        n_units = slot_size // per_unit_size
        local_kept = [i - start_idx for i in kept_in_vec]
        unit_labels_fn: Callable[[int], str] | None = None
        if vec_name == "bbox":
            unit_labels_fn = lambda upos: _label_position_slot(upos)
        elif vec_type == "keypoint":
            unit_labels_fn = lambda upos: _label_keypoint_slot(vec_name, upos)
        elif vec_type == "person_map":
            unit_labels_fn = lambda upos: _label_person_map_slot(vec_name, upos)

        logger.info("  %s  (%d/%d = %.1f%%)", vec_name, kept_count, total_in_vec, pct)
        if unit_labels_fn:
            for ui in range(n_units):
                offset = ui * per_unit_size
                kept_in_unit = [
                    i for i in local_kept if offset <= i < offset + per_unit_size
                ]
                if kept_in_unit:
                    kept_positions = [i - offset for i in kept_in_unit]
                    labels = [unit_labels_fn(p) for p in kept_positions]
                    logger.info("    unit %d: kept(%s)", ui, ", ".join(labels))
                elif n_units > 1:
                    pass  # skip units with nothing kept
            if kept_count == 0 and n_units == 1:
                all_labels = [unit_labels_fn(p) for p in range(per_unit_size)]
                logger.info("    Sub-features: %s", ", ".join(all_labels))
        return

    # Map vector -- Convert absolute indices to local slots and look up labels
    if vec_type == "map" and kept_count > 0:
        slot_labels = _load_map_slots(vec_name)
        logger.info("  %s  (%d/%d = %.1f%%)", vec_name, kept_count, total_in_vec, pct)
        for i in kept_in_vec:
            local_slot = i - start_idx
            label = (
                slot_labels[local_slot]
                if slot_labels and local_slot < len(slot_labels)
                else f"slot_{local_slot}"
            )
            logger.info("    [%d] %s", local_slot, label)
        return

    # Simple line per vector
    logger.info("  %-28s  %4d/%4d  (%5.1f%%)", vec_name, kept_count, total_in_vec, pct)


def list_filtered_features(transformer: DataTransformer, n_features_in: int) -> None:
    """
    Loads the cached filtered features for a layout of this width and prints a
    compact summary of which features survived the gain-based pruning.
    Multi-slot vectors (position, keypoint, person_map) are broken down by
    named sub-feature.
    """
    cached = transformer.training_loader.load_feature_rule(n_features_in)
    if cached is None:
        logger.info(
            "No feature rule cache found. Run data_transformer.filter_unused_features() first."
        )
        return

    kept_indices = cached
    mapping = get_feature_mapping_from_config()
    total = mapping["total_features"]
    kept_set = set(kept_indices.tolist())

    logger.info("Total features: %d", total)
    logger.info("Kept: %d, Dropped: %d", len(kept_indices), total - len(kept_indices))

    # Group kept indices by vector
    vec_kept: dict[str, list[int]] = {vn: [] for vn in mapping["vector_ranges"]}
    for i in sorted(kept_set):
        info = mapping["feature_to_vector"].get(i)
        if info:
            vec_kept[info["vector_name"]].append(i)

    logger.info("--- Feature survival summary ---")
    for vec_name in sorted(mapping["vector_ranges"].keys()):
        rng = mapping["vector_ranges"][vec_name]
        slot_size = rng["slot_size"]
        total_in_vec = rng["end_idx"] - rng["start_idx"]
        kept_in_vec = vec_kept.get(vec_name, [])

        _print_vector_summary(
            vec_name,
            rng.get("type", ""),
            kept_in_vec,
            total_in_vec,
            slot_size,
            rng.get("per_unit_size"),
            start_idx=rng["start_idx"],
        )
