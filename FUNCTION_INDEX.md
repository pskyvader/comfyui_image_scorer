# Current Structure Index

This is the live file and symbol inventory for `comfyui_image_scorer`. Paths are relative to this directory.

## Root files

| Path | Description |
|---|---|
| `LICENSE` | Module license text. |
| `pyproject.toml` | Package metadata, dependencies, scripts, and pytest configuration. |
| `uv.lock` | Locked Python dependency resolution. |
| `.gitignore` | Git exclusions for runtime and generated data. |
| `__init__.py` | ComfyUI node exports; adds the host ComfyUI root to `sys.path` before importing the node registry. |
| `scorer.py` | Command-line launcher. |
| `pyrightconfig.json` | Strict type-checker configuration. |
| `requirements.txt` | Generated dependency requirements. |
| `AGENTS.md` | Agent rules and engineering constraints. |
| `README.md` | Module purpose, goals, functionality, usage, and general architecture. |
| `FUNCTION_INDEX.md` | This current structure and symbol inventory. |
| `REORGANIZATION_PLAN.md` | Implementation and documentation roadmap. |

## Public symbols

The entries below anchor the main public interfaces and composition points.
Private helpers and exhaustive method listings are omitted when their names
are implementation details.

| Path | Symbol | Description |
|---|---|---|
| `__init__.py` | `NODE_CLASS_MAPPINGS` | ComfyUI node-name to class mapping. |
| `__init__.py` | `NODE_DISPLAY_NAME_MAPPINGS` | ComfyUI display-name mapping. |
| `scorer.py` | `main` | CLI launcher entry point. |
| `core/configuration/settings.py` | `Config` | Mutable configuration manager with JSON persistence. |
| `core/configuration/settings.py` | `config` | Process configuration object. |
| `core/observability/logger.py` | `get_logger` | Create a package module logger. |
| `core/observability/logger.py` | `capture_log_output` | Capture package logs and writes during a command. |
| `core/io/serialization.py` | `discover_files` | Discover image and metadata pairs in sorted, reproducible traversal order. |
| `core/io/serialization.py` | `collect_valid_files` | Collect valid files in parallel, returning results in input order. |
| `core/utilities/concurrency.py` | `parallel_batch` | Run a batch function sequentially. |
| `core/utilities/concurrency.py` | `parallel_for` | Run argument tuples through a worker pool, returning results in input order. |
| `domain/graph/chain_manager.py` | `ChainManager` | Own in-memory graph topology, chains, components, and comparison history. History entries are indexed by `(winner, loser)` so applying a comparison stays constant-time as the history grows. |
| `domain/graph/node_proxy.py` | `NodeProxy` | Expose graph node data and navigation. |
| `domain/graph/link_proxy.py` | `ComparisonRecord` | Public comparison edge record carrying the winner/loser link payload. |
| `domain/graph/link_proxy.py` | `LinkProxy` | Expose one comparison link record. |
| `domain/graph/chain_proxy.py` | `ChainProxy` | Expose one graph chain. |
| `domain/graph/component_proxy.py` | `ComponentProxy` | Expose one connected component. |
| `domain/analysis/trueskill.py` | `update_ratings` | Apply one winner/loser rating update. |
| `domain/analysis/trueskill.py` | `replay_ratings` | Replay comparison history into ratings. |
| `domain/comparison/algorithm/history_collapse.py` | `canonicalize_pair` | Canonicalize an unordered image pair into a stable sort key. |
| `domain/comparison/algorithm/history_collapse.py` | `safe_parse_timestamp` | Parse and normalize timestamps into comparable datetime values for deterministic ordering. |
| `domain/comparison/algorithm/history_collapse.py` | `collapse_comparison_history` | Collapse comparison history to a deterministic survivor set via missing-node, self-link, same-direction, and contradiction rules. |
| `domain/comparison/algorithm/graph_helpers.py` | `collapse_comparisons` | Collapse comparison history to a deterministic survivor set via missing-node, self-link, same-direction, and contradiction rules. |
| `domain/comparison/algorithm/graph_helpers.py` | `pair_key` | Canonicalize an unordered image pair. |
| `domain/comparison/algorithm/graph_helpers.py` | `safe_parse_timestamp` | Parse ISO timestamp strings into comparable datetime objects for deterministic ordering. |
| `domain/comparison/algorithm/merge_sort_ranker.py` | `select_pair_for_comparison` | Select the next ranking pair. |
| `domain/ports/graph.py` | `CrystalGraphPort` | Protocol graph/database boundary; `add_link` replaces `add_comparison`. |
| `domain/ports/repository.py` | `ImageRepository` | Image persistence protocol. |
| `domain/ports/repository.py` | `ComparisonRepository` | Comparison persistence protocol. |
| `domain/ports/files.py` | `FilePort` | Filesystem operations protocol: `read_json`, `write_json`, `file_exists`, `list_directory`, `make_directory`, `move_file`, `remove_file`, `ranked_root`, `compute_path`, `sync_metadata`, `clear_folder_cache`, `prewarm_folder_cache`, `deduplicate_scored`, and `cleanup_orphans`. |
| `domain/ports/loading.py` | `ModelLoader` | Vision, embedding, and attribute model loader protocol. |
| `application/services/graph_service.py` | `CrystalGraph` | Application graph facade and proxy factory. |
| `application/services/image_processor.py` | `ImageProcessor` | Ranked-file processing, rebuild, metadata sync, and rating replay service. |
| `application/services/image_processor.py` | `ImageProcessor.get_fast_total_count` | Counts candidate images with an application-owned `os.walk`/`Path.resolve` scan of the source tree; no port call. |
| `application/services/image_processor.py` | `ImageProcessor.process_next_batch` | Selects one candidate batch with an application-owned `os.walk` and `os.path.getmtime` ordering; candidate reads, writes, moves, and deletes are delegated to `FilePort`. |
| `application/services/image_processor.py` | `ImageProcessor.process_image_file` | Moves one image and its JSON into the ranked tree; every read, write, move, and delete is delegated to `FilePort`, with only the duplicate size check read locally. |
| `application/services/image_processor.py` | `ImageProcessor.reorganize_folder_structure` | Detects loose tier files with an application-owned `Path.glob`/`os.listdir`/`Path.is_dir` scan; JSON reads, tier-path computation, directory creation, and the moves are delegated to `FilePort`. |
| `application/services/image_processor.py` | `ImageProcessor.rebuild_database_from_ranked` | Rebuild flow; deduplication, orphan cleanup, metadata sync, and folder-cache control are delegated to `FilePort`. |
| `application/services/scoring_service.py` | `ScoringService` | Image scoring orchestration service. |
| `application/services/vector_list.py` | `VectorList` | Vector collection and derived-data service. |
| `application/hyperparameters/hyperparameter_optimizer.py` | `HpoRunner` | Hyperparameter search runner. |
| `adapters/comfyui/node_registry.py` | `NODE_CLASS_MAPPINGS` | Registered ComfyUI node classes. |
| `adapters/comfyui/nodes/aesthetic_score/node.py` | `AestheticScoreNode` | ComfyUI aesthetic scoring node. |
| `adapters/comfyui/nodes/aesthetic_score/node.py` | `calculate_score` | Node execution method returning scored and discarded images. |
| `adapters/server/main.py` | `main` | Start and initialize the Flask ranking server. |
| `adapters/cli/main.py` | `main` | Parse CLI arguments and dispatch commands. |
| `adapters/cli/commands/database.py` | `rebuild` | Explicitly rebuild the ranking database from ranked files. |
| `adapters/cli/commands/database.py` | `recalculate` | Replay existing comparison history into ratings. |
| `adapters/cli/commands/database.py` | `cleanup` | Clean stale comparisons and VACUUM the database. |
| `adapters/cli/commands/server.py` | `run_server` | Start the ranking server from CLI. |
| `adapters/cli/commands/vectors.py` | `run_split_vectors` | Build split vector files. |
| `adapters/cli/commands/vectors.py` | `run_full_vectors` | Build full vectors and text data. |
| `adapters/cli/commands/vectors.py` | `run_scores` | Build scores and comparisons. |
| `adapters/cli/commands/vectors.py` | `run_all` | Run the full build pipeline. |
| `adapters/cli/commands/training.py` | `train_model` | Train model from vectors and scores. |
| `adapters/cli/commands/training.py` | `run_hpo` | Run hyperparameter optimization. |
| `domain/comparison/constants.py` | `IMAGES_CACHE_TTL` | Image cache time-to-live constant. |
| `domain/comparison/constants.py` | `MAX_PAIR_CANDIDATES` | Maximum pair candidates for ranking. |
| `domain/comparison/constants.py` | `MIN_CHAIN_THRESHOLD` | Minimum chain threshold for pair selection. |
| `domain/analysis/image_analysis.py` | `ImageEntry` | Tuple type for image analysis entries. |
| `domain/analysis/image_analysis.py` | `ImageAnalysis` | Image metrics, metadata, and batch analysis orchestration class. |
| `domain/analysis/image_analysis.py` | `process_single_batch` | Process one batch of images through prepare, analyze, and save. |
| `domain/analysis/attribute_analysis.py` | `FaceAttributeAnalyzer` | Predicts perceived age, gender, and race from face images. |
| `domain/analysis/attribute_analysis.py` | `NSFWAnalyzer` | Predicts NSFW score from images. |
| `domain/analysis/attribute_analysis.py` | `AGE_LABELS` | Age category label set. |
| `domain/analysis/attribute_analysis.py` | `GENDER_LABELS` | Gender category label set. |
| `domain/analysis/attribute_analysis.py` | `RACE_LABELS` | Race category label set. |
| `domain/analysis/mediapipe_analysis.py` | `MediaPipeAnalyzer` | Detects faces and body pose through the injected MediaPipe provider. |
| `domain/analysis/mediapipe_analysis.py` | `POSE_LANDMARK_NAMES` | MediaPipe Pose landmark names in model output order. |
| `domain/analysis/trueskill.py` | `Rating` | Dataclass holding mu_skill and sigma_uncertainty. |
| `domain/analysis/trueskill.py` | `INITIAL_MEAN` | Initial rating mean constant. |
| `domain/analysis/trueskill.py` | `INITIAL_UNCERTAINTY` | Initial rating uncertainty constant. |
| `domain/comparison/comparison_recorder.py` | `ComparisonRecorder` | Comparison persistence and graph recording port consumer. |
| `domain/comparison/comparison_recorder.py` | `update_scores_after_comparison` | Update scores and ratings after one comparison. |
| `infrastructure/external_services/mediapipe_models.py` | `download_mediapipe_models` | Explicit MediaPipe model download and location handling. |
| `infrastructure/persistence/cleanup_orphans.py` | `cleanup_orphans` | Clean orphaned image and JSON companion files. |
| `infrastructure/persistence/folder_organizer.py` | `ensure_tier_structure` | Ensure score folders scored_0.0 through scored_1.0 exist. |
| `core/utilities/analysis.py` | `distribute` | Distribute values into named buckets by threshold. |
| `core/utilities/helpers.py` | `remove_directory` | Remove a directory and its contents. |
| `core/filesystem/paths.py` | `models_dir` | Path to the models output directory. |
| `core/filesystem/paths.py` | `mediapipe_models_dir` | Path to the downloaded MediaPipe models directory. |
| `core/filesystem/paths.py` | `training_plots_dir` | Path to the training plots directory. |
| `core/filesystem/paths.py` | `training_model` | Path to the training model artifact. |
| `infrastructure/persistence/database.py` | `get_db_connection` | Open a configured SQLite connection. |
| `infrastructure/persistence/images_repository.py` | `list_nodes` | Read image rows from SQLite. |
| `infrastructure/persistence/comparisons_repository.py` | `add_comparison` | Insert a comparison row into SQLite. |
| `infrastructure/persistence/comparisons_repository.py` | `add_comparisons_bulk` | Insert many comparison rows in one transaction, returning one id per input row. |
| `infrastructure/persistence/images_repository.py` | `add_images_bulk` | Insert many image rows in one transaction. |
| `infrastructure/persistence/images_repository.py` | `update_image_rating_states_bulk` | Apply many rating updates in one transaction. |
| `infrastructure/persistence/path_handler.py` | `pop_sync_counters` | Return and reset the metadata-sync written/skipped counters. |
| `infrastructure/persistence/file_manager.py` | `FileManager` | Concrete filesystem-port implementation. |
| `infrastructure/ml_models/model_loader.py` | `ModelLoader` | Concrete ML model loading implementation. |
| `infrastructure/ml_models/model_loader.py` | `ComfyVisionModel` | Vision-model wrapper that loads through ComfyUI memory management on every call. |
| `infrastructure/ml_models/model_loader.py` | `ComfyEmbeddingModel` | Embedding-model wrapper that loads through ComfyUI memory management on every call. |
| `infrastructure/ml_models/model_loader.py` | `ComfyAttributeModel` | Attribute-model wrapper that loads through ComfyUI memory management on every call. |
| `infrastructure/ml_models/model_loader.py` | `MultiTaskClipVisionModel` | Multi-head face attribute network (age, gender, race). |
| `infrastructure/cache/memory_cache.py` | `InMemoryCache` | In-memory TTL cache implementation. |

## Configuration and documentation

| Path | Description |
|---|---|
| `.github/workflows/check-deps.yml` | Dependency drift workflow. |
| `config/config.json` | Main runtime configuration. |
| `config/prepare_config.json` | Image preparation settings. |
| `config/ranking_config.json` | Ranking settings. |
| `config/training_config.json` | Training settings. |
| `config/vector_config.json` | Vector-generation settings. |
| `config/README.md` | Configuration directory guidance. |
| `docs/spike_config_schema.md` | Configuration schema investigation notes. |
| `experiments/depth_comparisons.ipynb` | Experimental depth-comparison notebook. |

## Core

| Path | Description |
|---|---|
| `core/__init__.py` | Core package marker and overview. |
| `core/configuration/__init__.py` | Configuration package exports. |
| `core/configuration/settings.py` | JSON configuration loading, validation, persistence, and mapping wrappers, plus the typed config payload shapes it validates against. |
| `core/filesystem/__init__.py` | Filesystem path package exports. |
| `core/filesystem/paths.py` | Runtime path constants for config, output, vectors, models, and caches. |
| `core/observability/__init__.py` | Logging package exports. |
| `core/observability/logger.py` | Structured logging, formatting, and synchronous log capture. |
| `core/io/__init__.py` | Serialization package exports. |
| `core/io/serialization.py` | JSON/JSONL serialization, atomic writes, image discovery, and batch collection. |
| `core/utilities/__init__.py` | Utility package exports. |
| `core/utilities/concurrency.py` | Sequential and threaded batch execution helpers. |
| `core/utilities/analysis.py` | Stateless analysis helpers. |
| `core/utilities/helpers.py` | Cache, model, vector, and image export cleanup helpers. |

## Domain

| Path | Description |
|---|---|
| `domain/__init__.py` | Domain package marker and overview. |
| `domain/graph/__init__.py` | Graph package exports. |
| `domain/graph/tests/test_chain_manager.py` | Chain-manager behavior tests. |
| `domain/vectors/__init__.py` | Vector package exports. |
| `domain/vectors/terms.py` | Prompt and term extraction structures. |
| `domain/vectors/helpers.py` | Vector helper functions. |
| `domain/vectors/number_vector.py` | Scalar numeric vector implementations. |
| `domain/vectors/keypoint_vector.py` | Keypoint vector implementation. |
| `domain/vectors/position_vector.py` | Position vector implementation. |
| `domain/vectors/map_vector.py` | Map-backed vector implementation. |
| `domain/vectors/person_map_vector.py` | Person-map vector implementation. |
| `domain/vectors/embedding_vector.py` | Embedding vector implementation. |
| `domain/vectors/image_vector.py` | Image vector base and processing behavior; calls the loaded vision model directly and reads its device from the model. |
| `domain/vectors/tests/__init__.py` | Vector test package marker. |
| `domain/vectors/tests/test_terms.py` | Term extraction tests. |
| `domain/analysis/mediapipe_analysis.py` | Face and pose analysis through MediaPipe. |
| `domain/analysis/attribute_analysis.py` | Age, gender, race, and NSFW model analysis; calls the loaded attribute models directly and reads their device from the model. |
| `domain/analysis/__init__.py` | Analysis package marker. |
| `domain/analysis/trueskill.py` | Rating update, replay, and public-score calculations. |
| `domain/analysis/image_analysis.py` | Image metrics, metadata, and batch analysis orchestration. |
| `domain/training/calibration.py` | Training calibration helpers. |
| `domain/training/__init__.py` | Training package marker. |
| `domain/training/grid.py` | Training grid definitions. |
| `domain/training/matrix_analysis.py` | Training matrix analysis. |
| `domain/data_transformation/__init__.py` | Transformation package marker. |
| `domain/data_transformation/data_transformer.py` | Feature transformation pipeline. |
| `domain/comparison/__init__.py` | Comparison package marker. |
| `domain/comparison/constants.py` | Comparison constants. |
| `domain/comparison/comparison_recorder.py` | Comparison persistence and graph recording port consumer. |
| `domain/comparison/algorithm/__init__.py` | Ranking algorithm package marker. |
| `domain/comparison/algorithm/phase_order.py` | Ranking phase ordering. |
| `domain/comparison/algorithm/graph_helpers.py` | Graph-query, pair-key, timestamp parsing, candidate-pool helpers, and history collapse. |
| `domain/comparison/algorithm/merge_sort_ranker.py` | Pair selection orchestration for merge-sort ranking. |
| `domain/comparison/algorithm/pair_active.py` | Active pair selection. |
| `domain/comparison/algorithm/view.py` | Ranking view and response shaping helpers. |
| `domain/loading/__init__.py` | Loading package marker. |
| `domain/ports/__init__.py` | Domain port exports. |
| `domain/ports/cache.py` | Cache provider protocol. |
| `domain/ports/ml_providers.py` | ML provider protocols. |
| `domain/ports/repository.py` | Image and comparison repository protocols. |
| `domain/ports/files.py` | Filesystem service protocol. |
| `domain/ports/loading.py` | Model, map, batch, and training loader protocols, plus the callable vision, embedding, attribute, transform, and processor surfaces those loaders return. |
| `domain/ports/loading.py` | `TrainingLoader` | Training-vector, model-artifact, and cached-rule loader protocol. |
| `domain/ports/loading.py` | `ModelTrainingService` | Trainer surface used to build and fit the feature-importance model. |
| `domain/ports/loading.py` | `ScoringModel` | Loaded training model surface used for scoring and plotting. |
| `domain/ports/graph.py` | CrystalGraph application port (Protocol). |

## Application

| Path | Description |
|---|---|
| `application/__init__.py` | Application package marker. |
| `application/services/__init__.py` | Application service exports. |
| `application/services/vector_list.py` | Vector collection and derived-data service. |
| `application/services/image_processor.py` | Ranked-image discovery, database rebuild, metadata sync, and rating replay. Ratings replay in stored link order so repeated rebuilds of unchanged files reproduce identical values. |
| `application/services/scoring_service.py` | ComfyUI-facing scoring orchestration. |
| `application/services/graph_service.py` | CrystalGraph facade over graph state and repositories. |
| `application/data_transform/__init__.py` | Application transformation package marker. |
| `application/data_transform/prepare_data.py` | Training-data preparation orchestration. |
| `application/hyperparameters/hyperparameter_optimizer.py` | Hyperparameter search orchestration. |
| `application/hyperparameters/__init__.py` | Hyperparameter package marker. |
| `application/analysis/__init__.py` | Application analysis package marker. |
| `application/analysis/run_parameter_analysis.py` | Parameter-analysis runner. |
| `application/analysis/run_matrix_analysis.py` | Matrix-analysis runner. |
| `application/analysis/run_stats.py` | Statistics runner. |
| `application/analysis/parameter_analysis.py` | Parameter-analysis service. |

## Adapters

| Path | Description |
|---|---|
| `adapters/__init__.py` | Adapter package marker. |
| `adapters/server/__init__.py` | Server adapter package marker. |
| `adapters/server/main.py` | Flask application factory and composition root. |
| `adapters/server/deps.py` | Server dependency container and CLI dependency conversion. |
| `adapters/server/compressed_image.py` | Image response compression helper. |
| `adapters/server/endpoints/__init__.py` | Endpoint package marker. |
| `adapters/server/endpoints/database.py` | Database HTTP endpoints. |
| `adapters/server/endpoints/analyze.py` | Analysis HTTP endpoints. |
| `adapters/server/endpoints/training.py` | Training HTTP endpoints. |
| `adapters/server/endpoints/build.py` | Build HTTP endpoints. |
| `adapters/server/endpoints/files.py` | File-management HTTP endpoints. |
| `adapters/server/endpoints/comparison.py` | Comparison HTTP endpoints. |
| `adapters/server/endpoints/gallery.py` | Gallery HTTP endpoints. |
| `adapters/server/endpoints/maps.py` | Map HTTP endpoints. |
| `adapters/server/tests/test_compressed_image.py` | Compressed-image adapter tests. |
| `adapters/server/tests/__init__.py` | Server test package marker. |
| `adapters/comfyui/__init__.py` | ComfyUI node exports. |
| `adapters/comfyui/node_registry.py` | Node registration mappings. |
| `adapters/comfyui/services.py` | ComfyUI composition root and service wiring. |
| `adapters/comfyui/nodes/__init__.py` | Node package marker. |
| `adapters/comfyui/nodes/aesthetic_score/__init__.py` | Aesthetic-score node package marker. |
| `adapters/comfyui/nodes/aesthetic_score/node.py` | AestheticScore node implementation. |
| `adapters/comfyui/input_adapters/__init__.py` | ComfyUI input adapter exports. |
| `adapters/comfyui/output_adapters/__init__.py` | ComfyUI output adapter exports. |
| `adapters/cli/__init__.py` | CLI package marker. |
| `adapters/cli/main.py` | Argument parser and command dispatch. |
| `adapters/cli/deps.py` | CLI dependency composition root. |
| `adapters/cli/commands/__init__.py` | CLI command package marker. |
| `adapters/cli/commands/server.py` | Server command. |
| `adapters/cli/commands/training.py` | Training and HPO commands. |
| `adapters/cli/commands/vectors.py` | Vector-generation commands. |
| `adapters/cli/commands/database.py` | Database maintenance commands. |

## Frontend assets

| Path | Description |
|---|---|
| `adapters/frontend/analyze/analyze.css` | Analysis page styles. |
| `adapters/frontend/analyze/analyze.html` | Analysis page markup. |
| `adapters/frontend/analyze/analyze.js` | Analysis page behavior. |
| `adapters/frontend/analyze/__init__.py` | Analysis frontend package marker. |
| `adapters/frontend/build/build.css` | Build page styles. |
| `adapters/frontend/build/build.html` | Build page markup. |
| `adapters/frontend/build/build.js` | Build page behavior. |
| `adapters/frontend/build/__init__.py` | Build frontend package marker. |
| `adapters/frontend/comparison/compare.css` | Comparison page styles. |
| `adapters/frontend/comparison/compare.html` | Comparison page markup. |
| `adapters/frontend/comparison/compare.js` | Comparison page controller. |
| `adapters/frontend/comparison/compare_queue.js` | Comparison queue behavior. |
| `adapters/frontend/comparison/compare_view.js` | Comparison view rendering. |
| `adapters/frontend/comparison/__init__.py` | Comparison frontend package marker. |
| `adapters/frontend/database/database.css` | Database page styles. |
| `adapters/frontend/database/database.html` | Database page markup. |
| `adapters/frontend/database/database.js` | Database page behavior. |
| `adapters/frontend/database/__init__.py` | Database frontend package marker. |
| `adapters/frontend/gallery/gallery.css` | Gallery page styles. |
| `adapters/frontend/gallery/gallery.html` | Gallery page markup. |
| `adapters/frontend/gallery/gallery.js` | Gallery page behavior. |
| `adapters/frontend/gallery/__init__.py` | Gallery frontend package marker. |
| `adapters/frontend/maps/maps.css` | Map page styles. |
| `adapters/frontend/maps/maps.html` | Map page markup. |
| `adapters/frontend/maps/__init__.py` | Maps frontend package marker. |
| `adapters/frontend/maps/graph_map/actions.js` | Graph-map actions. |
| `adapters/frontend/maps/graph_map/backend.js` | Graph-map data access. |
| `adapters/frontend/maps/graph_map/constants.js` | Graph-map constants. |
| `adapters/frontend/maps/graph_map/details_panel.js` | Graph-map details panel. |
| `adapters/frontend/maps/graph_map/dom_cache.js` | Graph-map DOM cache. |
| `adapters/frontend/maps/graph_map/events.js` | Graph-map event handling. |
| `adapters/frontend/maps/graph_map/filters.js` | Graph-map filters. |
| `adapters/frontend/maps/graph_map/hud.js` | Graph-map heads-up display. |
| `adapters/frontend/maps/graph_map/interactions.js` | Graph-map interaction handling. |
| `adapters/frontend/maps/graph_map/main.js` | Graph-map entry point. |
| `adapters/frontend/maps/graph_map/persistence.js` | Graph-map view persistence. |
| `adapters/frontend/maps/graph_map/physics.js` | Graph-map physics. |
| `adapters/frontend/maps/graph_map/three_renderer.js` | Three.js graph renderer. |
| `adapters/frontend/maps/graph_map/tooltip.js` | Graph-map tooltip rendering. |
| `adapters/frontend/maps/graph_map/utils.js` | Graph-map utilities. |
| `adapters/frontend/maps/graph_map/webgl_physics.js` | WebGL graph physics. |
| `adapters/frontend/maps/graph_map/__init__.py` | Graph-map package marker. |
| `adapters/frontend/training/training.css` | Training page styles. |
| `adapters/frontend/training/training.html` | Training page markup. |
| `adapters/frontend/training/training.js` | Training page behavior. |
| `adapters/frontend/training/__init__.py` | Training frontend package marker. |
| `adapters/frontend/shared/__init__.py` | Shared frontend package marker. |
| `adapters/frontend/shared/css/index.css` | Shared frontend styles. |
| `adapters/frontend/shared/html/index.html` | Shared frontend shell markup. |
| `adapters/frontend/shared/js/api.js` | Shared API client. |
| `adapters/frontend/shared/js/index.js` | Shared frontend bootstrap. |
| `adapters/frontend/shared/js/logger.js` | Shared browser logging. |
| `adapters/frontend/shared/js/utils.js` | Shared browser utilities. |

## Infrastructure

| Path | Description |
|---|---|
| `infrastructure/__init__.py` | Infrastructure package marker. |
| `infrastructure/persistence/__init__.py` | Persistence package exports. |
| `infrastructure/persistence/database.py` | SQLite connection and schema lifecycle. |
| `infrastructure/persistence/comparisons_repository.py` | Comparison table operations and history cleanup; uses domain comparison helpers for canonicalization and timestamp parsing. |
| `infrastructure/persistence/cleanup_orphans.py` | Orphaned-file cleanup. |
| `infrastructure/persistence/deduplicate_scored.py` | Duplicate scored-file cleanup; uses domain comparison helper for timestamp sorting. Cross-stem matching hashes only files whose byte size is shared, since a unique size cannot be a duplicate. |
| `infrastructure/persistence/folder_organizer.py` | Ranked-folder organization. |
| `infrastructure/persistence/images_repository.py` | Image table operations. |
| `infrastructure/persistence/path_handler.py` | Runtime path, image-file handling, and history sorting using domain comparison helper. |
| `infrastructure/persistence/file_manager.py` | Concrete filesystem-port implementation. |
| `infrastructure/external_services/__init__.py` | External-service package marker. |
| `infrastructure/external_services/mediapipe_models.py` | Explicit MediaPipe model download and location handling. |
| `infrastructure/ml_models/batch_sizer.py` | Model batch-size estimation; profiles CUDA memory through the model's ComfyUI patcher and returns a conservative size on non-CUDA devices. |
| `infrastructure/ml_models/model_loader.py` | Vision, embedding, and attribute model loading; wraps each model in a ComfyUI `ModelPatcher` and resolves its device through ComfyUI memory management. |
| `infrastructure/ml_models/model_loader.py` | `set_hub_offline` | Flips Hugging Face hub offline mode after import-time constants were mirrored. |
| `infrastructure/ml_models/model_loader.py` | `verify_models_present` | Raises when configured models are not downloaded locally. |
| `infrastructure/ml_models/model_loader.py` | `download_configured_models` | Downloads every configured model in download mode. |
| `infrastructure/ml_models/__init__.py` | ML-model package marker. |
| `infrastructure/ml_models/image_export.py` | Image export implementation. |
| `infrastructure/ml_models/plot.py` | Training and analysis plotting. |
| `infrastructure/ml_models/mediapipe_provider.py` | MediaPipe provider implementation. |
| `infrastructure/ml_models/training/__init__.py` | Training implementation package marker. |
| `infrastructure/ml_models/training/pair_data.py` | Pairwise training-data construction. |
| `infrastructure/ml_models/training/model_trainer.py` | Model training execution. |
| `infrastructure/loading/maps_loader.py` | Map configuration and value loading. |
| `infrastructure/loading/__init__.py` | Loading package exports. |
| `infrastructure/loading/training_loader.py` | Training-vector and model artifact loading. |
| `infrastructure/cache/__init__.py` | Cache package exports. |
| `infrastructure/cache/memory_cache.py` | In-memory TTL cache implementation. |

## Tests

| Path | Description |
|---|---|
| `tests/test_architecture.py` | Layer-import, database-boundary, and proxy-construction architecture gates. |
| `tests/test_deduplicate_scored.py` | Scored-tree deduplication over temporary directories: same-stem copies, filename conflicts, and cross-stem byte-identical detection across differing sizes. |
| `tests/test_general.py` | General command, endpoint, and integration contract tests. |
| `tests/test_graph_facade.py` | CrystalGraph facade behavior tests. |
| `tests/test_graph_helpers.py` | History-collapse and graph-helper algorithm tests. |
| `tests/test_image_processor.py` | `ImageProcessor` behavior: retained-versus-delegated filesystem operations, plus rebuild-from-ranked coverage (image rebuild, history replay and collapse, prompt tags, JSON sync, and run-to-run determinism). |

