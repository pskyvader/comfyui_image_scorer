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
| `adapters/comfyui/node_registry.py` | `NODE_DISPLAY_NAME_MAPPINGS` | ComfyUI display-name mapping. |
| `core/configuration/settings.py` | `Config` | Mutable configuration manager with JSON persistence. |
| `core/configuration/settings.py` | `config` | Process configuration object. |
| `core/observability/logger.py` | `get_logger` | Create a package module logger. |
| `core/observability/logger.py` | `capture_log_output` | Capture package logs and writes during a command. |
| `core/io/serialization.py` | `discover_files` | Discover image and metadata pairs in sorted, reproducible traversal order. |
| `core/io/serialization.py` | `collect_valid_files` | Collect valid files in parallel, returning results in input order. A positive `limit` stops after that many collected entries and cancels the queued work. |
| `core/io/serialization.py` | `load_single_jsonl` | Yield records from a JSONL file, skipping blank and optionally invalid lines. |
| `core/io/serialization.py` | `write_single_jsonl` | Write records to a JSONL file, replacing any existing contents. |
| `core/io/serialization.py` | `collect_single_file` | Parse one image and companion JSON pair into an entry tuple, or return None when it is not usable. |
| `core/io/serialization.py` | `load_json` | Load a JSON file with optional expected-type validation, returning the data and an error code. |
| `core/io/serialization.py` | `atomic_write_json` | Write JSON through a temporary file and replace, so readers never see a partial file. |
| `core/io/serialization.py` | `extract_prompt_tags` | Find the first non-empty positive prompt in a metadata structure, searching nested dicts. |
| `core/io/serialization.py` | `clean_json_metadata` | Normalize a companion JSON entry into the canonical ranked-metadata shape, stripping database-only fields. |
| `core/utilities/concurrency.py` | `parallel_batch` | Run a batch function sequentially. |
| `core/utilities/concurrency.py` | `parallel_for` | Run argument tuples through a worker pool, returning results in input order. |
| `domain/graph/chain_manager.py` | `ChainManager` | Own in-memory graph topology, chains, components, and link history. History entries are indexed by `(winner, loser)` so applying a link stays constant-time as the history grows. Per-chain main-member counts are tallied at build time so `get_main_chain_member_count` stays constant-time. Per-node transitive better/worse reach counts (`build_reach_counts`) are tallied at build time so `get_node_known_better_count`/`get_node_known_worse_count` stay constant-time; contradiction groups share counts, never count each other, and each member counts individually toward nodes outside the group. |
| `domain/graph/node_proxy.py` | `NodeProxy` | Expose graph node data and navigation. `link_count` reads the node's comparison count; `known_better_count`/`known_worse_count` read the chain manager's transitive reach counts. |
| `domain/graph/link_proxy.py` | `LinkRecord` | Public link record carrying the winner/loser edge payload. |
| `domain/graph/link_proxy.py` | `LinkProxy` | Expose one link record. |
| `domain/graph/chain_proxy.py` | `ChainProxy` | Expose one graph chain. `main_length` counts and `main_nodes` lists the nodes whose main chain is this chain; `is_main` is `main_length > 0`. |
| `domain/graph/component_proxy.py` | `ComponentProxy` | Expose one connected component. |
| `domain/analysis/trueskill.py` | `update_ratings` | Apply one winner/loser rating update. |
| `domain/analysis/trueskill.py` | `replay_ratings` | Replay comparison history into ratings. |
| `domain/comparison/algorithm/history_collapse.py` | `canonicalize_pair` | Canonicalize an unordered image pair into a stable sort key. |
| `domain/comparison/algorithm/history_collapse.py` | `safe_parse_timestamp` | Parse and normalize timestamps into comparable datetime values for deterministic ordering. |
| `domain/comparison/algorithm/history_collapse.py` | `collapse_comparison_history` | Collapse comparison history to a deterministic survivor set via missing-node, self-link, same-direction, and contradiction rules. |
| `domain/comparison/algorithm/graph_helpers.py` | `stable_seed_pool`, `count_exact_result_nodes`, `describe_median_status`, `is_collapsable_pair`, `filter_excluded_images` | Seed-pool selection, exact win/loss-count tally, middle-pool status (symmetric half-set bound, monotone excluded count, nearest-exit counts), collapsibility test, and exclusion filter for the pair-selection strategies. Pair canonicalization, timestamp ordering, and the history collapse are owned by `history_collapse.py`. |
| `domain/comparison/algorithm/merge_sort_ranker.py` | `select_pair_for_comparison` | Select the next ranking pair. |
| `domain/ports/graph.py` | `CrystalGraphPort` | Protocol graph/database boundary; `add_link` replaces `add_comparison` and `apply_link` replaces `apply_comparison`. `get_graph_stats` returns `GraphStructure`. |
| `domain/ports/graph.py` | `GraphStructure` | Typed payload of chain-manager-owned structure counts: `total_nodes`, `total_links`, `total_components`, `total_chains`, `longest_chain_depth`, `top_nodes_count`, `bottom_nodes_count`, and `built_at`. |
| `domain/ports/repository.py` | `ImageRepository` | Image persistence protocol. |
| `domain/ports/repository.py` | `ComparisonRepository` | Comparison persistence protocol. |
| `domain/ports/files.py` | `FilePort` | Filesystem operations protocol: `read_json`, `write_json`, `file_exists`, `list_directory`, `make_directory`, `move_file`, `remove_file`, `ranked_root`, `compute_path`, `sync_metadata`, `pop_sync_counters`, `clear_folder_cache`, `prewarm_folder_cache`, `deduplicate_scored`, and `cleanup_orphans`. |
| `domain/ports/loading.py` | `ModelLoader` | Vision, embedding, and attribute model loader protocol. |
| `application/services/graph_service.py` | `CrystalGraph` | Application graph facade and proxy factory. |
| `application/services/pairing_processor.py` | `PairingProcessor` | Ranked-file processing, rebuild, metadata sync, and rating replay service. |
| `application/services/pairing_processor.py` | `PairingProcessor.get_fast_total_count` | Counts candidate images with an application-owned `os.walk`/`Path.resolve` scan of the source tree; no port call. |
| `application/services/pairing_processor.py` | `PairingProcessor.process_next_batch` | Selects one candidate batch with an application-owned `os.walk` and `os.path.getmtime` ordering; each inserted image stores that source file mtime as `added_at`. Candidate reads, writes, moves, and deletes are delegated to `FilePort`. |
| `application/services/pairing_processor.py` | `PairingProcessor.process_image_file` | Moves one image and its JSON into the ranked tree; every read, write, move, and delete is delegated to `FilePort`, with only the duplicate size check read locally. |
| `application/services/pairing_processor.py` | `PairingProcessor.reorganize_folder_structure` | Detects loose tier files with an application-owned `Path.glob`/`os.listdir`/`Path.is_dir` scan; JSON reads, tier-path computation, directory creation, and the moves are delegated to `FilePort`. |
| `application/services/pairing_processor.py` | `PairingProcessor.rebuild_database_from_ranked` | Rebuild flow; each rebuilt row stores its ranked file mtime as `added_at`. Deduplication, orphan cleanup, metadata sync, and folder-cache control are delegated to `FilePort`. |
| `application/services/pairing_processor.py` | `PairingProcessor.sync_ranked_files_from_database` | Sync database state into ranked companion JSON without changing the database; collects the ranked entries with an application-owned scan and delegates every read, write, and move to `FilePort`. |
| `application/services/pairing_processor.py` | `PairingProcessor.sync_database_to_files` | Write one database row and its stored comparison history per collected ranked entry into companion JSON; the caller supplies the collected entries. |
| `application/services/scoring_service.py` | `ScoringService` | Image scoring orchestration service; applies the configured transforms in training order, in batch-size chunks, and guards the model against layout-width mismatch. |
| `application/services/vector_list.py` | `VectorList` | Vector collection and derived-data service. |
| `application/hyperparameters/hyperparameter_optimizer.py` | `HpoRunner` | Hyperparameter search runner. |
| `adapters/comfyui/node_registry.py` | `NODE_CLASS_MAPPINGS` | Registered ComfyUI node classes. |
| `adapters/comfyui/nodes/aesthetic_score/node.py` | `AestheticScoreNode` | ComfyUI aesthetic scoring node. |
| `adapters/comfyui/nodes/aesthetic_score/node.py` | `calculate_score` | Node execution method returning scored and discarded images. |
| `adapters/server/main.py` | `main` | Start and initialize the Flask ranking server. |
| `adapters/cli/main.py` | `main` | Parse CLI arguments and dispatch commands. |
| `application/analysis/run_stats.py` | `run_stats` | CLI entry point for `scorer.py analyze stats`; collects the payload once and prints it. |
| `application/analysis/run_stats.py` | `print_stats` | Print an already-collected `GraphStats`; the analyze endpoint calls it so the response log matches the CLI text. |
| `application/analysis/score_influence.py` | `ConditionData`, `CombinationInfluence`, `SparseCombinationSource`, `SparseCombinationArraySource` | Return data and protocols for condition preparation and indexed sparse combination fold/permutation analysis. |
| `application/analysis/score_influence.py` | `read_condition_elements`, `build_condition_data`, `analyze_combination_influence`, `analyze_sparse_combination_influence`, `load_score_influence_cache`, `save_score_influence_cache` | Extract per-image conditions, pack condition image masks, and measure dense or indexed sparse combinations with held-out folds and a shuffled-score noise floor. Condition families keep only a recorded-count floor; packed conditions require the minimum and drop conditions that match every analyzed image, keeping the first label for identical image masks. Measurement refuses totals over the maximum and skips folds below the minimum on both sides; the batched sparse passes mirror exactly that eligibility over the cached level arrays, with CSR multiplication for nulls and bincount eligibility plus score sums for folds. Cached NPZ results carry `combination_index` and `condition_names`, and the JSON sidecar stores the full parameter set — including the condition-vocabulary hash — behind its cache key. |
| `domain/training/frequent_combinations.py` | `CombinationFinder`, `SparseCombinationLevel`, `SparseCombinationResults`, `create_image_property_matrix`, `calculate_batch_capacity`, `count_shared_images`, `create_qualifying_extension_mask`, `find_qualifying_combinations`, `find_qualifying_combinations_blocked`, `create_possible_image_mask`, `create_candidate_image_masks`, `collect_level_image_matches`, `generate_combinations`, `generate_combinations_sparse` | Enumerate supported condition combinations through the original dense path or a sparse path that stores per-level combinations, offsets, and flat matching image IDs; sparse workers rebuild only batch-local matrices. Seeds keep every column above the minimum except columns matching every image (zeroed in the working matrix so they can re-appear as candidates); extension candidates need only the minimum, so over-maximum intersections stay stored unmeasured and their deeper in-range subsets remain reachable — the maximum gates measurement in analysis, not enumeration. Each level merge hashes matching image sets and keeps the first combination per identical set. `SparseCombinationResults.image_match_arrays` exposes level arrays for sparse analysis without copying them. |
| `adapters/cli/commands/database.py` | `rebuild` | Explicitly rebuild the ranking database from ranked files. |
| `adapters/cli/commands/database.py` | `sync` | Reload the graph and write database state back into ranked companion JSON. |
| `adapters/cli/commands/database.py` | `recalculate` | Replay existing comparison history into ratings. |
| `adapters/cli/commands/database.py` | `cleanup` | Clean stale comparisons and VACUUM the database. |
| `adapters/cli/commands/server.py` | `run_server` | Start the ranking server from CLI. |
| `adapters/cli/commands/vectors.py` | `run_split_vectors` | Build split vector files. |
| `adapters/cli/commands/vectors.py` | `run_full_vectors` | Build full vectors and text data. |
| `adapters/cli/commands/vectors.py` | `run_scores` | Build scores and comparisons. |
| `adapters/cli/commands/vectors.py` | `run_all` | Run the full build pipeline. |
| `adapters/cli/commands/training.py` | `train_model` | Train model from vectors and scores with the configured transform flags, saving the layout width and rule fingerprint beside the model. |
| `adapters/cli/commands/training.py` | `run_hpo` | Run hyperparameter optimization. |
| `domain/comparison/constants.py` | `IMAGES_CACHE_TTL` | Image cache time-to-live constant. |
| `domain/comparison/constants.py` | `MAX_PAIR_CANDIDATES` | Maximum pair candidates for ranking. |
| `domain/comparison/constants.py` | `MIN_CHAIN_THRESHOLD` | Minimum chain threshold for pair selection. |
| `domain/analysis/image_analysis.py` | `ImageEntry` | Tuple type for image analysis entries, shaped `(image_path, metadata, category, file_id)`. The key is the image path/id. |
| `domain/analysis/image_analysis.py` | `ImageAnalysis` | Image metrics, metadata, and batch analysis orchestration class. |
| `domain/analysis/image_analysis.py` | `process_single_batch` | Process one batch of images through prepare, analyze, and save. |
| `domain/analysis/image_analysis.py` | `analyze_images_from_paths` | Analyze discovered image paths through the vision, face, and NSFW passes. Returns entries keyed by image path/id; list order is batch-completion order and must not be relied on. |
| `domain/analysis/image_analysis.py` | `analyze_face_attributes` | Public entry point for the face attribute models, returning one age/gender/race distribution per image. |
| `domain/analysis/image_analysis.py` | `analyze_nsfw` | Public entry point for the NSFW model, returning one probability per image. |
| `domain/analysis/derived_features.py` | `pose_geometry` | Framing scalars from the 33 landmarks: head, shoulder and hip widths, torso and leg lengths, head and shoulder positions, lateral asymmetry, and the count of detected landmarks. Lengths are in MediaPipe's own units and are not clamped to the frame. |
| `domain/analysis/derived_features.py` | `face_geometry` | Face count, area fractions, centre position, and mean detector confidence from the bbox cells. |
| `domain/analysis/derived_features.py` | `dominant_category` | The most probable label and its probability from one person-attribute distribution. |
| `domain/analysis/derived_features.py` | `presence` | Whether a pose, a left hand and a right hand were detected, judged on landmark visibility above `POSE_VISIBILITY_THRESHOLD` rather than on landmark existence. |
| `domain/analysis/derived_features.py` | `prompt_features` | Prompt structure: length, term count and density, mean and maximum term weight, share of hand-written weights, nesting depth, connector count, duplicates, and normalised term position. |
| `domain/analysis/derived_features.py` | `mean_visibility` | Mean visibility over the named landmarks, ignoring the ones not detected. |
| `domain/analysis/derived_features.py` | `POSE_LANDMARK_NAMES`, `HAND_LANDMARKS`, `POSE_VISIBILITY_THRESHOLD` | Landmark vocabulary and the visibility threshold the presence splits use. |
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
| `domain/comparison/algorithm/view.py` | `describe_graph` | Whole-graph ranking measurements: score, rating-mu, rating-sigma and link-count distributions, the link-level histogram, the sigma-threshold above/below split, single-win, single-loss and ready counts, ranked/unranked totals, the highest- and lowest-scoring images, and the `structure` block collected from `CrystalGraphPort.get_graph_stats`. Reads every node field through `NodeProxy`. |
| `domain/comparison/algorithm/view.py` | `GraphStats` | Typed payload returned by `describe_graph`. |
| `domain/comparison/algorithm/view.py` | `Distribution` | Typed payload: a measured series' min, max, mean, and ascending equal-width histogram. |
| `domain/comparison/algorithm/view.py` | `ScoreBucket` | Typed payload: one histogram bucket's `lower`, `upper`, and `count`. |
| `domain/comparison/algorithm/view.py` | `RankedExtremes` | Typed payload: one row of a top/bottom score table. |
| `domain/comparison/algorithm/view.py` | `describe_pair` | Phase-specific pair payload from the two nodes: per-image payloads, whole-graph measurements and structure, chain totals with the chain_small settler's small-chain target (`minimum_chains_for_pairing`, or the count of chains at or below `chain_length_threshold`), the chain_middle median loop's `median_status` payload (resolved flag, candidate filename, remaining and excluded counts, middle bound, nearest-exit counts, comparison estimates), the exact-count node tally (`matching_count`) for the count-family phases, and the expected win probability. |
| `infrastructure/external_services/mediapipe_models.py` | `download_mediapipe_models` | Explicit MediaPipe model download and location handling. |
| `infrastructure/persistence/cleanup_orphans.py` | `cleanup_orphans` | Clean orphaned image and JSON companion files. |
| `infrastructure/persistence/folder_organizer.py` | `ensure_tier_structure` | Ensure score folders scored_0.0 through scored_1.0 exist. |
| `core/utilities/helpers.py` | `remove_directory` | Remove a directory and its contents. |
| `core/filesystem/paths.py` | `models_dir` | Path to the models output directory. |
| `core/filesystem/paths.py` | `mediapipe_models_dir` | Path to the downloaded MediaPipe models directory. |
| `core/filesystem/paths.py` | `training_plots_dir` | Path to the training plots directory. |
| `core/filesystem/paths.py` | `analysis_dir` | Path to the parameter-analysis output directory. |
| `core/filesystem/paths.py` | `training_model` | Path to the training model artifact. |
| `infrastructure/persistence/database.py` | `get_db_connection` | Open a configured SQLite connection. |
| `infrastructure/persistence/images_repository.py` | `list_nodes` | Read image rows from SQLite, including the stored `added_at` file mtime used for added-newest/oldest sorting. |
| `infrastructure/persistence/comparisons_repository.py` | `add_comparison` | Insert a comparison row into SQLite. |
| `infrastructure/persistence/comparisons_repository.py` | `add_comparisons_bulk` | Insert many comparison rows in one transaction, returning one id per input row. |
| `infrastructure/persistence/images_repository.py` | `add_images_bulk` | Insert many image rows in one transaction, preserving each row's `added_at` file mtime. |
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
| `experiments/parameter_and_analysis_correlation.ipynb` | Experimental notebook correlating every stored parameter and analysis value against the public score: generation scalars, the seven image metrics, face framing, pose geometry, detected attributes, and the categorical model/sampler/scheduler/LoRA parameters. Reads `comparisons.jsonl` and `text_data.jsonl` only, replays the score in memory, reports what the recorded comparison and feature rules kept, and re-measures the strongest correlations against the rule target. |
| `experiments/prompt_score_analysis.ipynb` | Experimental notebook analysing prompts alone: per-term score gaps with a Mann-Whitney p-value, BH correction and Cliff's delta; prompt-structure measures; model-concentration stratification; and TF-IDF prompt clusters with characteristic terms and example images. Re-measures the strongest term gaps against the recorded comparison rule. |
| `experiments/score_influence_threshold.ipynb` | Experimental notebook comparing single-condition effects and fixed condition-combination lifts against score thresholds and resampling noise floors. It replays ratings, extracts conditions, screens level-1 conditions to ones whose observed lift clears the threshold, enumerates supported combinations over the survivors, runs a family-wise bootstrap for singles and fold/permutation analysis for combinations, then plots the results and example images, listing under threshold-clearing rows the further conditions and condition tuples that cover exactly the same images. `SCORE_FORM` selects public or trueskill values; the threshold is converted using their observed spread ratio. Reusable condition extraction and combination influence calculations live in `application/analysis/score_influence.py`; combination enumeration lives in `domain/training/frequent_combinations.py`. Notebook settings and plotting remain in the notebook. |
| `experiments/depth_comparisons.ipynb` | Experimental notebook deriving implied comparison pairs from the chain manager: depth-1 brackets gain a 1/2 weight per better/worse pair, depth-2 brackets a 1/4 weight per recorded comparison's bracket. Confirmed pairs at or above the cutoff are filtered to ones absent from the database, with sigma and comparison-count gates, then, guarded by a preview flag in the notebook, inserted through `add_comparison` with score updates via `update_scores_after_comparison`; confirmed and near-miss pairs are plotted with example images. |
| `experiments/delete_high_comparison_files.ipynb` | Destructive ranked-file cleanup notebook. Rebuilds the graph from the database through `build_cli_deps`, selects node proxies whose `link_count` exceeds `MIN_COMPARISONS`, and computes the ranked companion JSON paths with `compute_path_from_filename`; a preview-mode flag guards the deletion and `LIMIT` caps the selection. |
| `experiments/loop_detection.ipynb` | Experimental notebook detecting contradiction cycles in the comparison graph: Tarjan SCCs, then an exact elementary-cycle DFS and a random-walk strategy under wall-clock limits. Each cycle is rotated to its highest-scored node, deduplicated, and the largest score-gap edges are selected for removal; the removal step, guarded by a preview flag in the notebook, deletes those comparison rows and decrements both images' comparison counts. Renders winner/loser image grids per loop with public and trueskill scores. |
| `experiments/random_order_scores.ipynb` | Experimental notebook measuring how far an image's score moves when the stored comparison history is replayed in random order. Scores every image in the database across `REPLAY_COUNT` random permutations, tracks the public and trueskill score forms side by side, and compares the recalculated production-order replay against the random-order spread. Reads only; writes nothing. |

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
| `core/utilities/helpers.py` | Cache, model, vector, and image export cleanup helpers. |
| `core/utilities/tests/test_concurrency.py` | Ordered worker-pool execution and result mapping tests. |

## Domain

| Path | Description |
|---|---|
| `domain/__init__.py` | Domain package marker and overview. |
| `domain/graph/__init__.py` | Graph package exports. |
| `domain/graph/chain_manager.py` | In-memory graph topology: directed edges, chains, components, and the link history that backs the ranking phases. Owns the structural counts — including the per-node transitive better/worse reach counts — every proxy and the graph facade expose. |
| `domain/graph/node_proxy.py` | Node proxy exposing one node's graph data and navigation. |
| `domain/graph/link_proxy.py` | `LinkRecord` and the proxy that exposes one comparison edge. |
| `domain/graph/chain_proxy.py` | Chain proxy exposing one ordering of nodes. |
| `domain/graph/component_proxy.py` | Component proxy exposing one connected subgraph. |
| `domain/graph/tests/__init__.py` | Graph test package marker. |
| `domain/graph/tests/test_chain_manager.py` | Chain-manager behavior tests, including the transitive better/worse reach counts. |
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
| `domain/training/matrix_analysis.py` | Training matrix analysis. `MatrixAnalyzer.export_records` returns one record per surviving cell, upper triangle only; the caller writes it, so an analysis notebook can chart the same rows. `get_text_weight` falls back to unit weight when a trailing weight marker is not a number, so one malformed prompt token cannot abort a whole run. |
| `domain/training/frequent_combinations.py` | Boolean image/property matrix creation and two combination enumeration paths. The dense path caches multiplied/intersected matrices and filters image rows; the sparse path caches combinations, offsets, and flat matching image IDs per level, and reconstructs batch-local matrices in workers using `core.utilities.concurrency.parallel_for`. Both paths seed from the minimum-support, non-full-coverage columns, bound candidate extensions to the minimum and maximum counts, and dedupe combinations whose matching image sets are identical at merge time. |
| `domain/training/statistics.py` | Statistical helpers for score comparisons: `benjamini_hochberg` returns BH-adjusted q-values, `mann_whitney_pvalue` gives the two-sided p-value for two score groups, `cliffs_delta` gives the effect size in O(n log n), and `correlation_with_ci` returns a Pearson or Spearman coefficient with a bootstrap interval and its p-value. `max_statistic_bootstrap` corrects a whole screened family of binary-condition effects with the Westfall-Young max-T bootstrap, returning a family-wise threshold that widens as conditions overlap, and reports progress through an optional callback. |
| `domain/training/statistics.py` | `CorrelationResult` | Dataclass holding a coefficient, its bootstrap interval, its p-value, and the sample size behind it. |
| `domain/training/statistics.py` | `MaxStatisticResult` | Dataclass holding each condition's observed effect, its family-wise p-value, the largest effect expected from noise alone at the requested confidence, and the resample count behind both. |
| `domain/analysis/tests/__init__.py`, `domain/analysis/tests/test_derived_features.py` | Derived-feature tests: landmark geometry, the presence splits and their threshold, face geometry, attribute dominance, and prompt structure. |
| `domain/training/tests/__init__.py`, `domain/training/tests/test_statistics.py`, `domain/training/tests/test_matrix_analysis.py`, `domain/training/tests/test_frequent_combinations.py` | Statistical helper tests and the matrix record-export tests, plus the frequent-combination tests: sparse seeds ignore the maximum and drop full-coverage columns, over-maximum parents are kept so deeper in-range subsets stay reachable, identical match sets dedupe at merge time, and the qualifying-extension mask respects the minimum and its ordering. |
| `domain/data_transformation/__init__.py` | Transformation package marker. |
| `domain/data_transformation/data_transformer.py` | Feature transformation pipeline: optional interaction expansion and gain-based feature filtering with width-validated cached rules and the composite rule fingerprint. |
| `domain/comparison/__init__.py` | Comparison package marker. |
| `domain/comparison/constants.py` | Comparison constants. |
| `domain/comparison/comparison_recorder.py` | Comparison persistence and graph recording port consumer. |
| `domain/comparison/algorithm/__init__.py` | Ranking algorithm package marker. |
| `domain/comparison/algorithm/phase_order.py` | Ranking phase metadata, direct phase dispatch, and on-demand selection data preparation. |
| `domain/comparison/algorithm/history_collapse.py` | Pair canonicalization, sortable timestamp parsing, and the pure history collapse that reduces imported comparisons to a deterministic survivor set. The single owner of all three. |
| `domain/comparison/algorithm/graph_helpers.py` | Graph-query, candidate-pool, and collapsibility helpers. |
| `domain/comparison/algorithm/pair_active.py` | `select_exact_count_pair`, `_middle_matching_count`, `_middle_anchor_key`, `_middle_opponent_key`, phase functions | Active pair selection for the ranking phases. `select_exact_count_pair` pairs an anchor with a pool of candidates sharing an exact win/loss count, filters already-compared pairs, and recalls inside the sigma range before a widest-gap fallback. The middle helpers rank candidates by their nearest pool exit and chain position, then rank opponents by matching-count proximity. Phase functions, in execution order: seed coverage, anchor insert, exact-count families, chain middle (picks the candidate nearest an exit, filters opponents before trimming to `lru_size`, then takes the closest-skill pair), uncertainty refine, chain small (pairs small-chain extreme nodes with long-chain main members so each chain grows past the length threshold), and fallback. Both pair members come from the supplied candidate nodes. |
| `domain/comparison/algorithm/pair_candidates.py` | `seed_pool_size`, seed-coverage pool helpers, anchor selectors, chain-member collectors | Candidate and anchor selection for the pairing phases. `collect_small_chain_anchors` returns each chain's extreme main nodes and `collect_long_chain_opponents` returns every main-chain member of the given chains; both filter to the supplied candidates, sort least-compared first, and cap by `lru_size`. |
| `domain/comparison/algorithm/pair_opponents.py` | `get_compatible_nodes`, opponent selectors | Self-exclusion and opponent-pool shaping for the pairing phases. `get_compatible_nodes` drops the anchor from a candidate pool and returns None when empty; the seed-coverage, anchor-insert, and uncertainty-refine selectors filter, sort, and cap their pools. |
| `domain/comparison/algorithm/pair_pipeline.py` | `Pair`, `form_candidate_pairs`, `filter_existing_pairs`, `filter_cross_chain_pairs`, `filter_uncertainty_refine_pairs`, `sigma_range_cap`, `closest_score_pair` | Pair formation, canonicalized existing-pair and same-path filtering, sigma range caps, and closest or widest score-gap selection. |
| `domain/comparison/algorithm/tests/test_pair_active_pipeline.py` | Active-pair candidate-boundary and fallback filtering test. |
| `domain/comparison/algorithm/tests/test_pair_active_anchor.py` | Anchor Insert seed-pool eligibility, opponent ordering, and load-spreading tests. |
| `domain/comparison/algorithm/tests/test_pair_active_refine.py` | Uncertainty Refine target selection, seed-pool eligibility, and load-spreading tests. |
| `domain/comparison/algorithm/tests/test_pair_active_rules.py` | Extracted phase-rule and shared exact-count selector tests, median flanker and small-chain settler tests, callback-free orchestration, and explicit intermediate results for nested calls. |
| `domain/comparison/algorithm/tests/test_phase_order.py` | Phase dispatch tests for direct calls and on-demand, reused selection data. |
| `domain/comparison/algorithm/tests/test_history_collapse.py` | History-collapse behavior tests: duplicate two-sided histories, contradictions, self-links, missing nodes, and deterministic survivor ordering. |
| `domain/comparison/algorithm/tests/test_pair_opponents.py` | Opponent-selection test: `get_compatible_nodes` returns None when only the anchor itself remains in the pool. |
| `domain/comparison/algorithm/merge_sort_ranker.py` | Pair selection orchestration for merge-sort ranking. |
| `domain/comparison/algorithm/view.py` | Ranking view and response shaping helpers. Owns the whole-graph ranking measurements in `describe_graph`; `describe_pair` is a projection of that payload. |
| `domain/comparison/tests/test_comparison_recorder.py` | Comparison recorder rating-state synchronization parity tests. |
| `domain/loading/__init__.py` | Loading package marker. |
| `domain/ports/__init__.py` | Domain port exports. |
| `domain/ports/cache.py` | Cache provider protocol. |
| `domain/ports/ml_providers.py` | ML provider protocols. |
| `domain/ports/repository.py` | Image and comparison repository protocols. |
| `domain/ports/comparison.py` | `PairingProcessorPort` | Full pairing-processor application protocol: processing state, batch processing, ranked-tree/database sync, and rebuild surface. |
| `domain/ports/files.py` | Filesystem service protocol. |
| `domain/ports/loading.py` | Model, map, batch, and training loader protocols, plus the callable vision, embedding, attribute, transform, and processor surfaces those loaders return. |
| `domain/ports/loading.py` | `TrainingLoader` | Training-vector, model-artifact, and cached-rule loader protocol; rule loads and saves are width-validated and memoize per-rule digests. |
| `domain/ports/loading.py` | `ModelTrainingService` | Complete trainer surface mirrored from `ModelTrainer`: metric directions, verbosity, build/fit/evaluate methods, callbacks, and result properties for the feature-importance model. |
| `domain/ports/loading.py` | `ScoringModel` | Loaded training model surface used for scoring and plotting. |
| `domain/ports/graph.py` | CrystalGraph application port (Protocol); `add_comparisons_bulk` shares the single insert transaction per batch. |

## Application

| Path | Description |
|---|---|
| `application/__init__.py` | Application package marker. |
| `application/services/__init__.py` | Application service exports. |
| `application/services/vector_list.py` | Vector collection and derived-data service. |
| `application/services/pairing_processor.py` | Ranked-image discovery, database rebuild, metadata sync, and rating replay. Ratings replay in stored link order so repeated rebuilds of unchanged files reproduce identical values. |
| `application/services/scoring_service.py` | ComfyUI-facing scoring orchestration; applies the configured transforms in training order in batch-size chunks and raises when the transformed width cannot match the model. |
| `application/services/graph_service.py` | CrystalGraph facade over graph state and repositories. `get_graph_stats` returns the `GraphStructure` counts owned by `ChainManager`. `add_image`, `add_images_bulk`, and `rebuild_from_database` intentionally leave the in-memory node map to be replaced wholesale by the next rebuild; `update_image_rating_state` and `update_image_rating_states_bulk` require the filename to be present in that map and raise `KeyError` otherwise. |
| `application/services/tests/test_pairing_processor.py` | PairingProcessor filesystem-boundary and rebuild behavior tests. |
| `application/data_transform/__init__.py` | Application transformation package marker. |
| `application/data_transform/prepare_data.py` | Training-data preparation orchestration. |
| `application/hyperparameters/hyperparameter_optimizer.py` | Hyperparameter search orchestration; `load_training_data` applies the optional transforms (interactions, feature filter, comparison filter) in order and returns the data with its rule fingerprint. |
| `application/hyperparameters/__init__.py` | Hyperparameter package marker. |
| `application/analysis/__init__.py` | Application analysis package marker. |
| `application/analysis/inputs.py` | `AnalysisInputs` and `collect_analysis_inputs`. Gathers the filename-keyed scores from the training loader and the prompt tags from the ranked database for both analyzers. Deliberately does not read `vectors.jsonl`, which holds embeddings and no score. |
| `application/analysis/row_fields.py` | Decoders for the text sidecar's values, which the writer stringifies: numbers arrive as strings and one-hot parameter maps as Python repr strings. Each helper prefers the real type and falls back to parsing. `as_object_list` covers the bbox, pose landmark and person-attribute columns, which the writer stores as repr strings of a list of dicts. |
| `application/analysis/feature_rows.py` | Flat feature table from scored text-sidecar rows, plus face, landmark, and detection-presence records for charts. |
| `application/analysis/score_influence.py` | Condition extraction and fixed-combination fold/permutation calculations for the score-threshold experiment. Dense inputs use a combination-to-row mapping; sparse inputs are read by combination index. Saved caches persist combination indices and condition names beside the analysis parameters; the caller supplies text rows and score mappings, and plotting remains in the notebook. |
| `application/analysis/tests/test_feature_rows.py` | Feature-table tests: cell decoding, the chart frames, the presence splits, and the missing-column error. |
| `application/analysis/run_stats.py` | Ranking-measurement printer. `run_stats` is the `scorer.py analyze stats` entry point and `print_stats` takes an already-collected `GraphStats`, so the analyze endpoint prints the same numbers the CLI does without walking the graph twice. |
| `application/analysis/run_parameter_analysis.py` | Parameter-analysis runner. Streams the text sidecar per analysis pass and writes to `core.filesystem.paths.analysis_dir`. |
| `application/analysis/run_matrix_analysis.py` | Matrix-analysis runner. `scored_rows` unpacks the sidecar's `{filename: payload}` rows and keeps only the generation parameters, because the build is quadratic in the parameter count. Writes `matrix_analysis.jsonl` under `analysis_dir` from `MatrixAnalyzer.export_records`. |
| `application/analysis/parameter_analysis.py` | Parameter-analysis service. Joins scores to rows by filename, extracts weighted prompt terms through `domain.vectors.terms.extract_terms`, and writes per-parameter, per-term and report artifacts under `core.filesystem.paths.analysis_dir`. |
| `application/analysis/parameter_analysis.py` | `analyze_term_correlations` | Scores every weighted prompt term in both prompt polarities and returns `TermCorrelationSummary` per polarity while still writing `term_correlations.json`. Terms below `MIN_TERM_IMAGES` are counted and left unranked. Each kept term reports its presence mean, the mean of the images lacking it, the gap between them, a Mann-Whitney p-value, its BH-corrected q-value, and Cliff's delta. |
| `application/analysis/parameter_analysis.py` | `TermCorrelationSummary` | One polarity's term records plus the row, unique-term, kept and dropped counts behind them. |
| `application/analysis/parameter_analysis.py` | `MIN_TERM_IMAGES` | Minimum images per term before it is ranked; 100 on this dataset's 14,531 distinct positive terms. |
| `application/analysis/tests/__init__.py` | Analysis test package marker. |
| `application/analysis/tests/test_analysis.py` | Analyzer schema tests: the sidecar row shape, the filename join, the stringified-column decoders, weighted term output with separated positive/negative groups, the matrix column whitelist, and that no analysis module references `vectors_file`. |
| `application/analysis/tests/test_score_influence.py` | Score-influence tests: numeric families surviving the recorded-count floor, full-coverage condition drops, first-label keeping for identical masks, bounded combination measurement, cache identifiers, cache keys that separate condition vocabularies, and that the batched sparse analysis reproduces every dense fold measurement and null lift across rounds, including refusing a total above the maximum. |

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
| `adapters/server/endpoints/gallery.py` | Gallery HTTP endpoints. Filtering, search, tag matching, sorting, and pagination are served by `GET /api/gallery/images`, whose `score_type` parameter selects the public, trueskill, or position score form for filtering, sorting, and the returned `score`; the same form drives opponent scores in `GET /api/gallery/history`. The `sort` parameter accepts `score_asc`/`score_desc`, `comparisons_asc`/`comparisons_desc`, and `added_asc`/`added_desc` (stored `added_at` file mtime, newest or oldest added). |
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
| `adapters/frontend/analyze/analyze.js` | Analysis page behavior. Extends `SectionView`. Renders the graph structure cards from the stats payload. |
| `adapters/frontend/build/build.css` | Build page styles. |
| `adapters/frontend/build/build.html` | Build page markup. |
| `adapters/frontend/build/build.js` | Build page behavior. Extends `SectionView` and adds the prepare-limit buttons. |
| `adapters/frontend/comparison/compare.css` | Comparison page styles. |
| `adapters/frontend/comparison/compare.html` | Comparison page markup. |
| `adapters/frontend/comparison/compare.js` | Comparison page controller. |
| `adapters/frontend/comparison/compare_queue.js` | Comparison queue behavior. |
| `adapters/frontend/comparison/compare_view.js` | Comparison view rendering. |
| `adapters/frontend/database/database.html` | Database page markup. |
| `adapters/frontend/database/database.js` | Database page behavior. Extends `SectionView`. |
| `adapters/frontend/gallery/gallery.css` | Gallery page styles. |
| `adapters/frontend/gallery/gallery.html` | Gallery page markup. |
| `adapters/frontend/gallery/gallery.js` | Gallery page behavior. A score-type selector (public, trueskill, or position score) drives filtering, sorting, score badges, modal metadata, and history scores, remapping the score filter sliders per form. Reports its selection to the router, which renders the shared Compare Selected control. |
| `adapters/frontend/maps/maps.css` | Map page styles. |
| `adapters/frontend/maps/maps.html` | Map page markup. |
| `adapters/frontend/maps/graph_map/actions.js` | Graph-map actions. |
| `adapters/frontend/maps/graph_map/backend.js` | Graph-map data access. |
| `adapters/frontend/maps/graph_map/constants.js` | Graph-map constants. |
| `adapters/frontend/maps/graph_map/details_panel.js` | Graph-map details panel. |
| `adapters/frontend/maps/graph_map/dom_cache.js` | Graph-map DOM cache. |
| `adapters/frontend/maps/graph_map/events.js` | Graph-map event handling. |
| `adapters/frontend/maps/graph_map/filters.js` | Graph-map filters. |
| `adapters/frontend/maps/graph_map/hud.js` | Graph-map heads-up display. Reports the node selection to the router. |
| `adapters/frontend/maps/graph_map/interactions.js` | Graph-map interaction handling. |
| `adapters/frontend/maps/graph_map/main.js` | Graph-map entry point. |
| `adapters/frontend/maps/graph_map/persistence.js` | Graph-map view persistence. |
| `adapters/frontend/maps/graph_map/physics.js` | Graph-map physics. |
| `adapters/frontend/maps/graph_map/three_renderer.js` | Three.js graph renderer. `_errorElement` is a boolean flag; the WebGL failure notice is appended to the container and left there. |
| `adapters/frontend/maps/graph_map/tooltip.js` | Graph-map tooltip rendering. |
| `adapters/frontend/maps/graph_map/utils.js` | Graph-map utilities. |
| `adapters/frontend/maps/graph_map/webgl_physics.js` | WebGL graph physics. |
| `adapters/frontend/training/training.html` | Training page markup. |
| `adapters/frontend/training/training.js` | Training page behavior. Extends `SectionView`. |
| `adapters/frontend/shared/css/index.css` | Shared frontend styles. Owns the section action and log chrome (`.section-title`, `.action-btn` and its `primary`/`danger` variants, `.log-area`, `.action-row`, `.action-desc`) scoped to the analyze, build, database and training containers, plus the range sliders used by the gallery and map controls. |
| `adapters/frontend/shared/html/index.html` | Shared frontend shell markup. Hosts the Compare Selected control, which the router shows only for the gallery and chain-map sections. |
| `adapters/frontend/shared/js/api.js` | Shared API client. |
| `adapters/frontend/shared/js/index.js` | Shared frontend bootstrap and SPA router. Owns Compare Selected visibility and the selected count, and delegates the control's click to the current section instance's `compareSelected`. |
| `adapters/frontend/shared/js/logger.js` | Shared browser logging. Messages take optional detail arguments rendered into the log target and passed to the console; there is no timing argument. |
| `adapters/frontend/shared/js/section_view.js` | `SectionView` base class for the analyze, build, database and training views. Owns the container lookup, the scoped logger, the `data-action` and clear-log wiring, and the log echo. Subclasses supply a container id and logger name and override `afterInit` or `bindActions`. |
| `adapters/frontend/shared/js/utils.js` | Shared browser utilities. |

## Infrastructure

| Path | Description |
|---|---|
| `infrastructure/__init__.py` | Infrastructure package marker. |
| `infrastructure/persistence/__init__.py` | Persistence package exports. |
| `infrastructure/persistence/database.py` | SQLite connection and schema lifecycle. |
| `infrastructure/persistence/comparisons_repository.py` | Comparison table operations and history cleanup; uses domain comparison helpers for canonicalization and timestamp parsing. |
| `infrastructure/persistence/cleanup_orphans.py` | Orphaned-file cleanup. |
| `infrastructure/persistence/deduplicate_scored.py` | Duplicate scored-file cleanup; sorts merged entries through `domain.comparison.algorithm.history_collapse.safe_parse_timestamp`. Cross-stem matching hashes only files whose byte size is shared, since a unique size cannot be a duplicate. |
| `infrastructure/persistence/folder_organizer.py` | Ranked-folder organization. |
| `infrastructure/persistence/images_repository.py` | Image table operations. |
| `infrastructure/persistence/path_handler.py` | Runtime path, image-file handling, and history sorting through `domain.comparison.algorithm.history_collapse.safe_parse_timestamp`. |
| `infrastructure/persistence/file_manager.py` | Concrete filesystem-port implementation. |
| `infrastructure/persistence/tests/test_bulk_repository.py` | Bulk repository writes must match per-row writes, including ids. |
| `infrastructure/persistence/tests/test_deduplicate_scored.py` | Deduplication tests over temporary ranked trees, including same-stem and cross-stem matches. |
| `infrastructure/external_services/__init__.py` | External-service package marker. |
| `infrastructure/external_services/mediapipe_models.py` | Explicit MediaPipe model download and location handling. |
| `infrastructure/ml_models/batch_sizer.py` | Model batch-size estimation; profiles CUDA memory through the model's ComfyUI patcher and returns a conservative size on non-CUDA devices. |
| `infrastructure/ml_models/model_loader.py` | Vision, embedding, and attribute model loading; wraps each model in a ComfyUI `ModelPatcher` and resolves its device through ComfyUI memory management. |
| `infrastructure/ml_models/model_loader.py` | `set_hub_offline` | Flips Hugging Face hub offline mode after import-time constants were mirrored. |
| `infrastructure/ml_models/model_loader.py` | `verify_models_present` | Raises when configured models are not downloaded locally. |
| `infrastructure/ml_models/model_loader.py` | `download_configured_models` | Downloads every configured model in download mode. |
| `infrastructure/ml_models/__init__.py` | ML-model package marker. |
| `infrastructure/ml_models/tests/__init__.py` | ML-model test package marker. |
| `infrastructure/ml_models/tests/test_model_loader.py` | Patcher-wrapper tests: each vision, embedding, and attribute forward runs under `torch.no_grad`, so no autograd graph is retained across a batch. |
| `infrastructure/ml_models/image_export.py` | Image export implementation. |
| `infrastructure/ml_models/plot.py` | Training and analysis plotting. Also holds `plot_correlation_bars`, `plot_correlation_heatmap`, `plot_image_grid`, and the face and pose position charts the analysis notebooks call. |
| `infrastructure/ml_models/mediapipe_provider.py` | MediaPipe provider implementation. |
| `infrastructure/ml_models/training/__init__.py` | Training implementation package marker. |
| `infrastructure/ml_models/training/pair_data.py` | Pairwise training-data construction. |
| `infrastructure/ml_models/training/model_trainer.py` | Model training execution. |
| `infrastructure/loading/maps_loader.py` | Map configuration and value loading. |
| `infrastructure/loading/__init__.py` | Loading package exports. |
| `infrastructure/loading/training_loader.py` | Training-vector and model artifact loading, including width-validated transform rules and their digests. |
| `infrastructure/cache/__init__.py` | Cache package exports. |
| `infrastructure/cache/memory_cache.py` | In-memory TTL cache implementation. |

## Tests

| Path | Description |
|---|---|
| `tests/conftest.py` | Shared transform-pipeline fixtures: temp rule paths, a training loader stubbed with keyed data, and a deterministic fake trainer. |
| `tests/test_architecture.py` | Layer-import, database-boundary, and proxy-construction architecture gates. |
| `tests/test_general.py` | General command, endpoint, and integration contract tests, including the AestheticScoreNode wiring and delegation tests. |
| `tests/test_graph_facade.py` | CrystalGraph facade and persistence-adapter integration tests. |
| `tests/test_rule_guards.py` | Transform-rule cache behavior: width validation, missing-rule errors, stale and legacy rule cache misses, digest memoization, and fingerprint composition. |
| `tests/test_training_data_pipeline.py` | `load_training_data` flag-matrix tests over the real loader and a fake trainer: raw passthrough, interactions before feature filter, comparison filtering, and fingerprint changes. |
| `infrastructure/ml_models/tests/test_batch_sizer.py` | Batch calibration through the public `get()` with a scripted allocator: marginal-cost acceptance, stale-fit ceiling, and the least-squares fit. |
