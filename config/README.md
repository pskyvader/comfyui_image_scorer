# Configuration Files

JSON configuration files for the image scorer system.

- [`config.json`](config.json) — Root config: `image_root` pointing to the ComfyUI output directory, and relative paths to sub-configs for each pipeline stage.
- `prepare_config.json` — Image preparation settings.
- `vector_config.json` — Vector/term extraction settings.
- `training_config.json` — Model training hyperparameters.
- `ranking_config.json` — Ranking/comparison graph settings.
