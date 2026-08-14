import os
from ..configuration.settings import config
from pathlib import Path

root: Path = Path(__file__).parents[2]
# config_dir: str = os.path.join(root, "config")
output_dir: str = os.path.join(root, "output")
maps_dir: str = os.path.join(output_dir, "maps")
cache_file: str = os.path.join(output_dir, "cache.db")


if config["image_root"] == "":
    raise RuntimeError(
        "core.filesystem.paths: image_root not configured. "
        "Adapter composition root must set config['image_root'] before importing core."
    )
image_root: str = config["image_root"]
image_root_processed: str = os.path.join(image_root, "scored")

vectors_size_file: str = os.path.join(output_dir, "image_vector_size.json")

vectors_dir: str = os.path.join(output_dir, "vectors")
split_dir: str = os.path.join(vectors_dir, "split")
vectors_file: str = os.path.join(vectors_dir, "vectors.jsonl")
scores_file: str = os.path.join(vectors_dir, "scores.jsonl")
comparisons_file: str = os.path.join(vectors_dir, "comparisons.jsonl")
index_file: str = os.path.join(vectors_dir, "index.jsonl")
text_data_file: str = os.path.join(vectors_dir, "text_data.jsonl")


models_dir: str = os.path.join(output_dir, "models")
mediapipe_models_dir: str = os.path.join(output_dir, "downloaded_models")
training_plots_dir: str = os.path.join(output_dir, "training", "plots")

training_model: str = os.path.join(models_dir, "model.npz")
vectors_data: str = os.path.join(models_dir, "vectors.npz")
scores_data: str = os.path.join(models_dir, "scores.npz")
comparisons_data: str = os.path.join(models_dir, "comparisons.npz")
feature_rule: str = os.path.join(models_dir, "feature_rule.npz")
comparison_rule: str = os.path.join(models_dir, "comparison_rule.npz")
interaction_data: str = os.path.join(models_dir, "interaction_data.npz")
