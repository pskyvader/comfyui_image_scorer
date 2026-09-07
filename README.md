# ComfyUI Image Scorer

ComfyUI custom-node module for scoring generated images, comparing images in pairs, maintaining ranking history, browsing galleries, inspecting graph and latent maps, analyzing image attributes, preparing training data, and tuning ranking or prediction models.

## Goals

- Provide an efficient aesthetic-scoring node for ComfyUI workflows.
- Preserve comparison history and reproducible ranking state.
- Support analysis, visualization, training, and model-assisted inspection.
- Keep domain behavior testable independently from Flask, ComfyUI, SQLite, and filesystem implementations.
- Keep runtime use local and offline except for explicit model downloads.

## Functionality

- **Aesthetic scoring:** score images and route accepted or discarded images in ComfyUI.
- **Pairwise ranking:** record winner/loser comparisons and maintain graph chains, components, links, and rating state.
- **Database operations:** inspect, clean, rebuild, and recalculate ranking data from ranked image metadata.
- **Image analysis:** calculate visual, face, pose, NSFW, prompt, and metadata features.
- **Vector and model workflows:** build image vectors, train models, optimize hyperparameters, and export derived artifacts.
- **Web views:** use the local server for comparison, gallery, database, analysis, training, and graph/map views.

## Architecture

The module separates reusable computation from framework and infrastructure concerns:

```text
                    +------------------+
                    |    ComfyUI node  |
                    +--------+---------+
                             |
                    +--------v---------+
                    |     adapters     |
                    | CLI, server, web |
                    +--------+---------+
                             |
                    +--------v---------+
                    |   application    |
                    | orchestration    |
                    +--------+---------+
                             |
                    +--------v---------+
                    |      domain      |
                    | rules, graph, ML |
                    +--------+---------+
                             |
                    +--------v---------+
                    |       core       |
                    | config, IO, util |
                    +------------------+

                    infrastructure
          SQLite, files, loaders, models, cache
          is injected at composition roots.
```

## Runtime

The module lives under `ComfyUI/custom_nodes/` and is loaded by ComfyUI. Its dependencies are installed in the ComfyUI virtual environment; the package itself is not installed as a separate distribution.

On Windows, activate the environment before running commands:

```powershell
& "E:\ComfyUI\.venv\Scripts\Activate.ps1"
```

The command-line entry points are:

```text
python scorer.py --help
python scorer.py server --help
python scorer.py build all --help
python scorer.py database rebuild --help
```

Install or refresh dependencies from the ComfyUI environment when the module
requirements change:

```powershell
uv pip compile pyproject.toml -o requirements.txt
pip install -r requirements.txt
```

Useful workflows include:

```text
python scorer.py server
python scorer.py build split-vectors --limit 100
python scorer.py build all
python scorer.py database cleanup
python scorer.py database recalculate
python scorer.py training train-model
```

`database rebuild` is destructive: it deduplicates and cleans ranked files,
clears the image and comparison tables, and repopulates them from ranked-file
metadata. Use `database recalculate` when existing history should remain and
only ratings should be replayed. CLI operations and command endpoints operate
synchronously; server startup may run maintenance work in background workers.

The local web server exposes the analysis, build, comparison, database, gallery, maps, and training workflows.

## ComfyUI node

The registered node is `AestheticScore` (`AestheticScoreNode` in the Scoring
category). It accepts an image, threshold, prompt strings, generation
settings, model and LoRA names/strength, and minimum/maximum image counts. It
returns `images`, `discarded images`, `Available`, and `score`. The node
delegates application behavior to the scoring service.

## Runtime data

Configuration is user-managed. Derived vectors, maps, model artifacts, plots, and the SQLite cache are runtime data. A database rebuild is an explicit, destructive operation: it clears and repopulates image and comparison tables from ranked-file metadata. Startup graph loading is an in-memory operation and is distinct from that database rebuild.
