# Function Index — comfyui_image_scorer

All functions, methods, and classes grouped by file (paths relative to `comfyui_image_scorer`). Files are ordered by layer following the layout in `README.md` and `REORGANIZATION_PLAN.md`; see the last section for paths those documents describe that are not yet on disk.

## `__init__.py`

### Module-level functions

| Name | Description |
|---|---|
| `__getattr__(name)` | Lazy-loads `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` from `adapters.comfyui` |

---

## `adapters/cli/commands/database.py`

### Module-level functions

| Name | Description |
|---|---|
| `cleanup(**kwargs)` | CLI command that cleans stale comparisons and vacuums the database, returning the comparison count |
| `rebuild(**kwargs)` | CLI command that rebuilds the database from ranked files via the ImageProcessor and returns 0 |
| `recalculate(**kwargs)` | CLI command that resets ratings, replays all comparisons through TrueSkill, updates scores, and returns status code |

---

## `adapters/cli/commands/server.py`

### Module-level functions

| Name | Description |
|---|---|
| `run_server(host="0.0.0.0", port=5001, **kwargs)` | CLI command that initializes the database and ranking system, then starts the Flask app, returning 0; optional `debug` kwarg forwarded to Flask |

---

## `adapters/cli/commands/training.py`

### Module-level functions

| Name | Description |
|---|---|
| `train_model()` | CLI command that loads comparison-filtered training data, trains the LightGBM model with the `training.top1` config, saves it with its metrics, writes `training_curves.png`, `score_distribution.png`, and `prediction_accuracy.png` to `output/training/plots/`, and returns 0 |
| `run_hpo(**kwargs)` | CLI command that runs hyperparameter optimization cycles with optional `cycles` / `optimization_steps` / `max_combos` overrides (config defaults otherwise), logs the best result, and returns 0 |

---

## `adapters/cli/commands/vectors.py`

### Module-level functions

| Name | Description |
|---|---|
| `run_split_vectors(limit=0, batch=False)` | CLI command that builds split vector files, optionally in looping batch mode, and removes derived caches when new data was added |
| `run_full_vectors(**kwargs)` | CLI command that builds full vector and text data from existing splits and returns 0 |
| `run_scores(**kwargs)` | CLI command that rebuilds scores and comparisons and returns 0 |
| `run_all(limit=0, batch=False, **kwargs)` | CLI command that runs the full build pipeline with optional limit and batch flags and returns 0 |

---

## `adapters/cli/main.py`

### Module-level functions

| Name | Description |
|---|---|
| `_add_build_parser(subparsers)` | Adds the build subparser with split-vectors, full-vectors, scores, and all commands and returns it |
| `_add_training_parser(subparsers)` | Adds the training subparser with train-model and hpo commands and returns it |
| `_add_database_parser(subparsers)` | Adds the database subparser with cleanup, rebuild, and recalculate commands and returns it |
| `_add_files_parser(subparsers)` | Adds the files subparser with remove, download, and cleanup commands and returns the parsers |
| `_add_analyze_parser(subparsers)` | Adds the analyze subparser with parameters, matrix, and stats commands and returns it |
| `main()` | Parses argv, dispatches to the selected command, returns its exit code |

---

## `adapters/comfyui/__init__.py`

| Name | Description |
|---|---|
| `__all__` | Exports ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS'] |
| `NODE_CLASS_MAPPINGS` | Re-exported from `.node_registry` |
| `NODE_DISPLAY_NAME_MAPPINGS` | Re-exported from `.node_registry` |

---

## `adapters/comfyui/nodes/aesthetic_score/__init__.py`

| Name | Description |
|---|---|
| `__all__` | Exports ['AestheticScoreNode'] |
| `AestheticScoreNode` | Re-exported from `.node` |

---

## `adapters/comfyui/nodes/aesthetic_score/node.py`

### Class `AestheticScoreNode`

| Name | Description |
|---|---|
| `__init__()` | Initializes the node's scoring service |
| `INPUT_TYPES()` (classmethod) | Classmethod returning the required node inputs and their defaults |
| `calculate_score(image, threshold, positive, negative, steps, cfg, sampler, scheduler, model_name, lora_name, lora_strength, min_images, max_images)` | Verifies models are present, scores the image via the scoring service, and returns images, availability, and score list |

---

## `adapters/server/endpoints/analysis.py`

> Analysis API - endpoints for statistics, parameter analysis, and reporting

### Module-level functions

| Name | Description |
|---|---|
| `get_stats()` | Flask route: returns statistics about images, comparisons, score buckets, and graph stats as JSON |
| `analyze_parameters()` | Flask route: starts a background parameter analysis task and returns the task body as JSON |
| `analyze_matrix()` | Flask route: starts a background matrix analysis task and returns the task body as JSON |
| `get_report_file()` | Flask route: returns the content of an absolute-path JSON or JSONL report file as JSON with validation errors |
| `get_task(task_id)` | Flask route: returns task status as JSON, or a 404 error dict when the task is unknown |
| `cancel_task(task_id)` | Flask route: cancels a background task and returns status JSON, or a 404 error dict when cancellation fails |
| `register_analysis_routes(app)` | Registers the analysis blueprint on the Flask app |

---

## `adapters/server/endpoints/comparison.py`

> Ranking API v2 endpoints

### Module-level functions

| Name | Description |
|---|---|
| `_get_processor()` | Returns the image processor from the Flask app, or None |
| `_get_level_progress_stats(all_images)` | Computes ranking level progress from comparison counts and graph stats, returning a stats dict |
| `get_ranking_config()` | Flask route: returns the ranking configuration and computed seed size as JSON |
| `get_ranking_phases()` | Flask route: returns the ranking phases as JSON |
| `get_status()` | Flask route: returns ranking progress, comparison counts, and level stats as JSON |
| `get_next_pair()` | Flask route: selects the next image pair for comparison and returns both image descriptions and pair payload as JSON, or an error dict |
| `reset_ranking_queue()` | Flask route: force-clears the processor's recent-image cache and returns success JSON |
| `skip_image()` | Flask route: adds the submitted filename to the recent-images cache and returns ok JSON |
| `submit_comparison()` | Flask route: validates and records a comparison, then returns updated scores for both images as JSON |
| `sync_all_to_json()` | Flask route: syncs every image's metadata to its companion JSON and returns synced and error counts as JSON |
| `register_ranking_routes(app)` | Registers the ranking blueprint on the Flask app |

### Class `_ComparisonRepoAdapter`

| Name | Description |
|---|---|
| `get_all_comparisons(weight)` | Returns all comparisons, optionally filtered by weight |
| `get_total_comparisons()` | Returns the total number of comparisons |
| `comparison_exists_for_pair(a, b)` | Returns whether a comparison already exists for the given pair |
| `add_comparison(filename_a, filename_b, winner, weight, transitive_depth, timestamp)` | Delegates to the repository to record a comparison between two filenames with a winner |
| `get_images_with_only_wins()` | Returns the images that have only winning comparisons |
| `get_images_with_only_losses()` | Returns the images that have only losing comparisons |

### Class `_ImageRepoAdapter`

| Name | Description |
|---|---|
| `get_image(filename)` | Returns the image record for the given filename |
| `get_all_images()` | Returns all image records |
| `update_image_rating_state(filename, score, rating_mu, rating_sigma, comparison_count, touch_timestamp)` | Delegates to the repository to update an image's rating state |

### Class `_PathSyncerAdapter`

| Name | Description |
|---|---|
| `sync_image_metadata_to_json(filename, score, rating_mu, rating_sigma, comparison_count, all_comparisons)` | Delegates to the path handler to sync image metadata to its companion JSON file |

---

## `adapters/server/endpoints/data_transform.py`

> Data Transform API - endpoints for data preparation and transformation

### Module-level functions

| Name | Description |
|---|---|
| `_get_processor()` | Returns the image processor from the Flask app, or None |
| `prepare_data()` | Flask route: starts a background data preparation task honoring the request flags and returns the task body as JSON |
| `scan_import()` | Flask route: runs one batch of image processing over the image root and returns the stats as JSON |
| `delete_vectors()` | Flask route: starts a background task that deletes full vector files, keeping splits, and returns the task body as JSON |
| `get_task(task_id)` | Flask route: returns task status as JSON, or a 404 error dict when the task is unknown |
| `register_data_transform_routes(app)` | Registers the data blueprint on the Flask app |

---

## `adapters/server/endpoints/database.py`

> Database endpoints - API routes for maintenance and file operations

### Module-level functions

| Name | Description |
|---|---|
| `_get_processor()` | Returns the image processor from the Flask app, or None |
| `get_status()` | Flask route: returns database image and comparison counts as JSON |
| `normalize()` | Flask route: cleans comparisons, rebuilds the graph from the database, and returns stats as JSON |
| `rebuild_database()` | Flask route: starts a background rebuild of the database from ranked files and returns the task body as JSON |
| `sync_all()` | Flask route: starts a background task syncing all image metadata to companion JSON and returns the task body as JSON |
| `run_cleanup_orphans()` | Flask route: runs orphan cleanup with the requested dry-run flag and returns the result as JSON |
| `run_deduplicate()` | Flask route: runs scored-file deduplication with the requested dry-run and limit and returns the result as JSON |
| `get_task(task_id)` | Flask route: returns task status as JSON, or a 404 error dict when the task is unknown |
| `register_database_routes(app)` | Registers the database blueprint on the Flask app |

---

## `adapters/server/endpoints/gallery.py`

> Gallery API - endpoints for viewing and filtering ranked images

### Module-level functions

| Name | Description |
|---|---|
| `list_images()` | Flask route: filters, sorts, and paginates image entries, returning them as JSON |
| `get_image_info(filename)` | Flask route: returns a single image's metadata as JSON, or a 404 error dict when missing |
| `search_images()` | Flask route: returns images matching a filename query and score range as JSON |
| `get_image_history(filename)` | Flask route: returns an image's win and loss history against opponents as JSON |
| `register_gallery_routes(app)` | Registers the gallery blueprint on the Flask app |

---

## `adapters/server/endpoints/maps.py`

> Maps API - endpoints for chain visualizations (graph data)

### Module-level functions

| Name | Description |
|---|---|
| `get_graph_data()` | Flask route: rebuilds the graph if stale and returns nodes, edges, components, and chains as JSON |
| `register_maps_routes(app)` | Registers the maps blueprint on the Flask app |

---

## `adapters/server/endpoints/training.py`

> Training & Hyperparameters API - endpoints for model training and HPO

### Module-level functions

| Name | Description |
|---|---|
| `reset_configs()` | Flask route: resets hyperparameter configuration and returns success JSON |
| `run_hpo()` | Flask route: starts a background hyperparameter optimization task using config values and returns the task body as JSON |
| `delete_models()` | Flask route: removes trained models from disk and returns success JSON |
| `get_task(task_id)` | Flask route: returns task status as JSON, or a 404 error dict when the task is unknown |
| `get_training_config()` | Flask route: returns the training configuration as JSON |
| `update_training_config()` | Flask route: merges or overwrites the training configuration from the request payload and returns the updated config as JSON |
| `register_training_routes(app)` | Registers the training blueprint on the Flask app |

---

## `adapters/server/main.py`

> Main server - Flask application for ranking system

> **Scheduled deletion (REORGANIZATION_PLAN §0.1):** `start_background_scanner` is dead — defined but never invoked.

### Module-level functions

| Name | Description |
|---|---|
| `serve_index()` | Flask route: serves the main frontend index.html |
| `serve_css(filename)` | Flask route: serves a CSS file from the server frontend |
| `serve_js(filename)` | Flask route: serves a JS file from the server frontend |
| `serve_section_static(section, filename)` | Flask route: serves static files from a section frontend, returning a 404 error dict for unknown sections |
| `serve_ranked_image(filepath)` | Flask route: serves a ranked image by direct path or filename lookup with no-cache headers, returning a 404 error dict when missing |
| `serve_image_by_name(filename)` | Flask route: serves an image by filename, preferring the score-based path, returning a 404 error dict when not found |
| `serve_image_alias(filename)` | Flask route: delegates to serve_image_by_name for the /image/ alias path |
| `catch_api_404(path)` | Flask route: returns a 404 error dict for unknown /api/ paths |
| `serve_html(filename)` | Flask route: serves a fallback HTML file from the server frontend |
| `not_found(e)` | Flask error handler: returns a 404 error dict for unmatched routes |
| `server_error(e)` | Flask error handler: logs the exception and returns a 500 error dict |
| `scanner_task(img_root)` | Background loop that processes batches of images and sleeps, doubling the interval up to 600s when nothing was added |
| `start_background_scanner(img_root)` | Starts a daemon scanner thread if one is not already running |
| `startup_worker()` | Ensures the tier structure exists, then runs the scanner task over the image root |
| `init_ranking_system()` | Starts the background startup worker thread and returns True |
| `main()` | Parses server arguments, configures logging, initializes the ranking system, and runs the Flask app |

### Module-level constants

| Symbol | Description |
|---|---|
| `SECTION_FRONTENDS` | Maps section names to their frontend directories served under /static/ |
| `SERVER_FRONTEND` | Path to the server's own frontend directory |

---

## `adapters/server/processor.py`

> Image processor - discovery, initialization, and rebuild flow

### Class `ImageProcessor`

> Process uninitialized images with parallel workers

| Name | Description |
|---|---|
| `__init__(max_workers)` | Stores ranking config values, initializes locks, processed-image set, and LRU deques, then syncs from the database |
| `_extract_prompt_tags(data)` | Recursively finds the first non-empty positive_prompt string in the metadata dict |
| `clean_json_metadata(json_data, default_score, filename)` | Strips ranking bookkeeping fields from JSON metadata and returns a cleaned copy with default rating values and prompt tags |
| `process_image_file(image_path)` | Processes a single raw image and companion JSON into the ranked tree, returning success, message, score, dest name, db existence, and prompt tags |
| `sync_processed_images_from_db()` | Reloads the processed-images set from the database and logs the synchronized count |
| `get_fast_total_count(source_dir)` | Walks the source dir excluding ranked and output roots, counts image files, stores and returns the total |
| `process_next_batch(source_dir, batch_size)` | Discovers unprocessed images, processes a batch with a thread pool, inserts new ratings into the database, and returns stats |
| `rebuild_database_from_ranked()` | Reorganizes folders, deduplicates and cleans files, clears and repopulates the database and comparison history from ranked JSON, recomputes ratings, and syncs metadata |
| `_recompute_ratings_from_database_history()` | Resets ratings, replays comparison history through TrueSkill, updates each image's rating state, and returns the count updated |
| `reorganize_folder_structure()` | Moves loose image and JSON files in scored tiers into score-based subfolders, returning nothing |
| `clear_old_cache(force)` | Clears the LRU caches when full or when forced, otherwise trims 75 percent of the least recently used items |

---

## `application/analysis/run_matrix_analysis.py`

### Module-level functions

| Name | Description |
|---|---|
| `run_matrix_analysis()` | Loads vectors and text data, builds the matrix, calculates statistics, and exports them to matrix_analysis.json |

---

## `application/analysis/run_parameter_analysis.py`

### Module-level functions

| Name | Description |
|---|---|
| `run_parameter_analysis()` | Loads vectors and text data and runs the ParameterAnalyzer to generate an analysis report |

---

## `application/analysis/run_stats.py`

### Module-level functions

| Name | Description |
|---|---|
| `_distribute(values, bins)` | Groups float values into equally spaced range buckets with formatted labels |
| `run_stats()` | Loads all images and comparisons and prints score, rating, and comparison-count statistics plus top and bottom 10 images |

---

## `application/data_transform/config/maps.py`

### Module-level functions

| Name | Description |
|---|---|
| `register_map_values(processed_data)` | Registers map and person_map values found in processed data entries into the global maps_list |

---

## `application/data_transform/prepare_data.py`

### Module-level functions

| Name | Description |
|---|---|
| `build_split_files(limit)` | Collects unprocessed images, analyzes them, builds and joins vectors, writes all dataset files, and returns a summary |
| `build_full_files()` | Rebuilds the full vectors, index, text, scores, and comparisons files from existing split data |
| `run_prepare(limit, batch)` | Runs split file builds repeatedly until no new files are found when batch is set, then builds the full files |
| `run_rebuild_scores_only()` | Rebuilds the scores and comparisons jsonl files from the database records for existing vectors |

---

## `application/hyperparameters/hyperparameter_optimizer.py`

### Module-level functions

| Name | Description |
|---|---|
| `generate_random_config()` | Builds a random hyperparameter config dict for the current training objective |
| `generate_fastest_setup()` | Builds a config targeting the fastest training setup for the objective |
| `generate_slowest_setup()` | Builds a config targeting the highest-quality (slowest) setup for the objective |
| `crossover_config(cfg1, cfg2)` | Merges two configs into a new child by picking each key from one parent |
| `reset_hyperparameters()` | Resets the HPO state to the initial 5-config population (random, random, slowest, fastest, random) and persists it |
| `load_training_data(filter_comparisons)` | Loads keyed vectors and scores, filters unused features, and returns aligned X/y arrays; when `filter_comparisons` is True keeps only files with enough comparisons (scores replayed on the kept subset), otherwise keeps every scored file with its full-history score |
| `hpo_cycle(X, y, optimization_steps=100, max_combos=4, cycle=0)` | Runs one HPO cycle: optimizes each population config with per-key variation steps, sorts configs by score, breeds the next generation (top 2 parents + 2 crossover children + 1 random), persists state, and returns the new state dict |
| `run_hpo_cycles(cycles=None, optimization_steps=None, max_combos=None)` | Runs multiple HPO cycles over the top1..top5 configs, breeding the next generation after each cycle; `None` values fall back to `config["training"]` defaults; returns the per-cycle results list |

---

## `application/services/graph_service.py`

### Class `CrystalGraph`

> Main graph API. All access through get_* methods returning proxy objects

| Name | Description |
|---|---|
| `__init__(image_repo, comparison_repo)` | Creates internal `ChainManager`, empty image/comparison stores, optionally stores repos |
| `get_node_chain_length(filename)` | Returns length of the node's main chain (0 if none) |
| `get_main_chain_member_count(chain_id)` | Returns how many nodes have `chain_id` as their main chain |
| `rebuild_from_database(images, comparisons)` | Full rebuild: loads images/comparisons from repos or args, builds ChainManager, builds chain map |
| `apply_comparison(winner, loser)` | Delegates a single comparison to the ChainManager |
| `is_cache_stale()` | Checks whether the DB comparison count differs from the snapshot |
| `get_node(node_id)` | Returns `NodeProxy` for given node ID or `None` |
| `get_all_nodes(only_top, only_bottom)` | Returns all `NodeProxy` objects, optionally filtered by top/bottom |
| `get_chain(node_id, chain_id)` | Returns `ChainProxy` looked up by node ID or chain ID |
| `get_all_chains(min_length, sort_order)` | Returns all `(ChainProxy, [(NodeProxy, is_main)])` tuples, filtered by length and sorted |
| `get_component(node_id, component_id, chain_id)` | Returns `ComponentProxy` looked up by node, component, or chain ID |
| `get_all_components()` | Returns all `ComponentProxy` objects |
| `get_all_links()` | Returns all `(winner_node, loser_node)` directed edge tuples |
| `get_graph_stats()` | Returns a dict of graph statistics |
| `are_in_same_path(img1, img2)` | Checks if two images are in the same path (reachable in either direction) |
| `get_chains_map()` | Builds and caches chains map grouped by length |

### Class `_LazyImageRepo`

| Name | Description |
|---|---|
| `get_all_images()` | Lazily imports and returns all images from the images repository |
| `get_image(filename)` | Lazily imports and returns a single image record by filename |

### Class `_LazyComparisonRepo`

| Name | Description |
|---|---|
| `get_all_comparisons()` | Lazily imports and returns all comparisons from the comparisons repository |
| `get_total_comparisons()` | Lazily imports and returns the total comparison count |

---

## `application/services/scoring_service.py`

### Class `ScoringService`

> Application service that encapsulates the full scoring workflow

| Name | Description |
|---|---|
| `__init__()` | Sets the model loader, batch sizer, and default batch size for scoring |
| `score(image, threshold, positive, negative, steps, cfg, sampler, scheduler, model_name, lora_name, lora_strength, min_images, max_images)` | Validates inputs, analyzes the image batch, predicts scores, selects images above the threshold, and returns selected and discarded tensors with scores |
| `_predict_scores(model, filtered_vectors)` | Predicts scores from the model, handling binary, multiclass, and lambdarank objectives with calibration |

---

## `application/services/vector_list.py`

### Class `VectorList`

| Name | Description |
|---|---|
| `__init__(raw_data, read_only)` | Configures per-type vectors, loads split files and scores when writable, and ingests raw data computing public scores |
| `configure_sorted_vectors()` | Instantiates the matching vector class for every vector config entry |
| `_exclude_present_entry(current_vector)` | Returns entries whose file ids are not already present in the given vector's list |
| `_exclude_present_image_path(current_vector)` | Returns image paths whose file ids are not already present in the image vector's path list |
| `create_vectors()` | Parses new entries and builds vector lists for every configured vector by type |
| `validate_and_convert(data, name, target_size)` | Converts data to a float32 array, raising when the row width mismatches the target slot size |
| `filter_missing_vectors()` | Narrows unique_ids to those present in the scores map and every vector list |
| `join_vectors()` | Stacks each vector's per-id rows column-wise into the final vector matrix |
| `convert_text_list(clean_arrays, current_list, name)` | Merges a named value mapping into per-file-id dictionaries keyed by vector name |
| `join_text_data()` | Builds the final text data as one dictionary per id containing each vector's raw values |
| `join_comparison_data()` | Builds comparison rows with indexes, scores, score differences, and weights for comparisons whose files are in the index |
| `update_lists()` | Populates vectors_list, text_list, index_list, scores_list, and comparisons_list from current state |
| `load_split_files()` | Loads per-type split jsonl files into unique_ids and vector and value lists, registering map values |
| `load_split_scores()` | Loads scores from the scores file, rebuilding missing scores from database rating records |
| `export_split_files()` | Writes per-type split jsonl files with id, raw, and vector values and caches them in memory |

---

## `core/configuration/settings.py`

### Module-level functions

| Name | Description |
|---|---|
| `_get_config_file(path)` | Resolves a relative path against `PROJECT_ROOT`; returns absolute `Path` |
| `_load_raw_config(path)` | Loads and returns a JSON config dict from disk (empty dict on failure) |
| `_save_raw_config(data, path)` | Writes a config dict to a JSON file on disk, creating parent dirs |
| `ensure_dir(path)` | Creates directories with `os.makedirs(..., exist_ok=True)` |

### Module-level constants

| Symbol | Description |
|---|---|
| `PROJECT_ROOT` | Absolute path of the package root (3 levels up from this file) |
| `CONFIG_FILE` | Path to `config/config.json` |
| `SUB_CONFIG_MAPPING` | Maps section names to their sub-config file names (prepare, training, vector, ranking) |

### Class `AutoSaveDict` (MutableMapping)

| Name | Description |
|---|---|
| `__init__(data, save_callback)` | Stores the underlying data dict and save callback |
| `get(key, default)` | Gets a value; raises `ValueError` if default is provided (banned) |
| `__getitem__(key)` | Gets item by key, wrapping nested dicts in another `AutoSaveDict` |
| `__setitem__(key, value)` | Sets item and triggers save callback |
| `__delitem__(key)` | Deletes item and triggers save callback |
| `__iter__()` | Yields keys from underlying data |
| `__len__()` | Returns number of keys |
| `copy()` | Returns a shallow copy of the underlying dict |
| `__repr__()` | Returns repr of underlying dict |

### Class `Config` (MutableMapping)

> Configuration Manager

| Name | Description |
|---|---|
| `__init__(config_file)` | Initialises with a root config path, empty caches |
| `get(key, default)` | Gets a value; raises `ValueError` if default is provided (banned) |
| `_get_root()` | Lazy-loads and caches the root config data from disk |
| `_save_root()` | Writes root config back to disk if loaded |
| `_get_sub(section)` | Loads and caches a sub-config section from its file path |
| `_save_sub(section)` | Writes a sub-config section back to its file |
| `__getitem__(key)` | Looks up key in subconfigs (wraps in `AutoSaveDict`), then root, then deep subconfig keys |
| `__setitem__(key, value)` | Sets value in the appropriate config section (subconfig or root) |
| `__delitem__(key)` | Deletes key from the appropriate section |
| `__iter__()` | Iterates over all keys from root, subconfig section names, and subconfig data |
| `__len__()` | Returns total number of unique keys |
| `clear()` | Clears all caches so next access re-reads from disk |

---

## `core/filesystem/paths.py`

> **Scheduled deletion (REORGANIZATION_PLAN §0.1):** `hyperparameters_statistics` is a dead constant — no callers (the legacy HPO ledger was dropped in the rewrite).

### Module-level functions

| Name | Description |
|---|---|
| `_resolve_image_root()` | Returns the configured image root, falling back to ComfyUI's output directory |

### Module-level constants

| Symbol | Description |
|---|---|
| `root` | Project root path (3 levels up from this file) |
| `output_dir` | Path to `output/` directory |
| `maps_dir` | Path to `output/maps/` |
| `cache_file` | Path to `output/cache.db` |
| `image_root` | Image root from config |
| `image_root_processed` | `image_root` + `/scored` |
| `vectors_size_file` | Path to `output/image_vector_size.json` |
| `hyperparameters_statistics` | Path to `output/hyperparameters_statistics.json` |
| `vectors_dir` | Path to `output/vectors/` |
| `split_dir` | Path to `output/vectors/split/` |
| `vectors_file` | Path to `output/vectors/vectors.jsonl` |
| `scores_file` | Path to `output/vectors/scores.jsonl` |
| `comparisons_file` | Path to `output/vectors/comparisons.jsonl` |
| `index_file` | Path to `output/vectors/index.jsonl` |
| `text_data_file` | Path to `output/vectors/text_data.jsonl` |
| `models_dir` | Path to `output/models/` |
| `mediapipe_models_dir` | Path to `output/downloaded_models/` |
| `training_plots_dir` | Path to `output/training/plots/` |
| `training_model` | Path to `output/models/model.npz` |
| `vectors_data` | Path to `output/models/vectors.npz` |
| `scores_data` | Path to `output/models/scores.npz` |
| `comparisons_data` | Path to `output/models/comparisons.npz` |
| `feature_rule` | Path to `output/models/feature_rule.npz` |
| `comparison_rule` | Path to `output/models/comparison_rule.npz` |
| `interaction_data` | Path to `output/models/interaction_data.npz` |

---

## `core/io/serialization.py`

> **Scheduled deletion (REORGANIZATION_PLAN §0.1):** `load_single_entry_mapping` is dead — no callers anywhere.

### Module-level functions

| Name | Description |
|---|---|
| `load_single_jsonl(filename, skip_invalid)` | Yields parsed JSON objects from each non-empty line of a JSONL file |
| `write_single_jsonl(filename, data, mode)` | Writes a list of items to a JSONL file with a tqdm progress bar |
| `discover_files(root)` | Walks a directory yielding `(image_path, metadata_path)` for images with a companion `.json` file |
| `collect_single_file(file)` | Processes one image/metadata pair, returning `(img_path, metadata, timestamp, file_id)` or `None` |
| `collect_valid_files(files, max_workers, scored_only)` | Collects valid image/metadata pairs from discovered files using a thread pool |
| `_recursive_parse_json(obj, path)` | Recursively parses JSON-encoded strings within a deserialized JSON structure |
| `load_json(path, expect)` | Loads a JSON file, optionally validates its type, returns `(data, err)` |
| `atomic_write_json(path, data)` | Atomically writes JSON to a file via a temp file and `os.replace` |
| `load_single_entry_mapping(path)` | Loads a JSON dict with exactly one key, returns `(payload, key, err)` |

---

## `core/observability/logger.py`

> Shared backend logging utilities

> **Scheduled deletion (REORGANIZATION_PLAN §0.1):** `set_log_filter_hook` and `log_message` are dead (no callers; `set_log_filter_hook` is also a dead import at `adapters/server/main.py:19`), and the `TaskLogHandler` class is never instantiated.

### Module-level functions

| Name | Description |
|---|---|
| `_custom_find_caller(stack_info, stacklevel)` | Custom `findCaller` that skips `logger.py` frames to report the true caller |
| `_is_progress_line(line)` | Returns `True` if line contains progress indicators (`%`, `|`, `img/s`, etc.) |
| `set_log_filter_hook(fn)` | Installs a global hook called for every output line |
| `get_logger(module_name)` | Returns root logger if `None`, else a `ModuleLogger` |
| `configure_package_logging(level, fmt)` | Sets up console handler with `CustomFormatter`, configures package-level logger |
| `log_message(module_name, level_name, message, start_timer, task_id)` | Convenience wrapper that delegates to `SharedLogger.log(...)` |

### Class `_TaskOutput`

> Single point of control for ALL task output: logs, progress, prints,

| Name | Description |
|---|---|
| `context(task_id)` (classmethod) | Context manager that sets the current thread's task_id |
| `current_task_id()` (classmethod) | Returns current thread's task_id or `None` |
| `register_buffer(task_id, lines)` (classmethod) | Associates a list buffer with a task_id |
| `unregister_buffer(task_id)` (classmethod) | Removes the buffer for a task_id |
| `has_buffer(task_id)` (classmethod) | Checks whether a buffer exists for a task_id |
| `write(task_id, line)` (classmethod) | Writes line to task buffer, applies filter hook, trims to `MAX_LINES`, optionally broadcasts via SSE |

### Class `CaptureStream` (io.TextIOBase)

> Wraps stdout/stderr during a task

| Name | Description |
|---|---|
| `__init__(lines, original_stream)` | Stores lines buffer, original stream, optional task_id |
| `write(s)` | Writes to original stream, accumulates buffer, splits on newlines |
| `_process_line(line)` | Routes completed line to `_TaskOutput` or local buffer |
| `flush()` | Flushes the original stream |
| `_flush_remaining()` | Flushes any remaining buffered content |

### Class `SSELogBroadcaster`

> Broadcasts log lines to all connected SSE clients in real time

| Name | Description |
|---|---|
| `_ensure_dispatch()` (classmethod) | Starts the background dispatch thread once |
| `_dispatch_loop()` (classmethod) | Background loop that batches up to 50 lines into subscriber queues |
| `subscribe()` (classmethod) | Registers a new SSE subscriber, returns `(sub_id, Queue)` |
| `unsubscribe(sub_id)` (classmethod) | Removes a subscriber by ID |
| `broadcast(line)` (classmethod) | Queues a log line for dispatch to all subscribers |

### Class `_DynamicModuleFilter` (logging.Filter)

| Name | Description |
|---|---|
| `filter(record)` | Returns `SharedLogger.should_emit(record.name)` |

### Class `TaskLogHandler` (logging.Handler)

> Capture unmanaged logging records for a single task thread

| Name | Description |
|---|---|
| `__init__(lines, owner_thread_id)` | Stores buffer and the owning thread's ID |
| `emit(record)` | Formats and writes log records that bypass `SharedLogger` into task buffer/SSE stream |

### Class `ModuleLogger`

| Name | Description |
|---|---|
| `__init__(module_name)` | Stores the module name |
| `_underlying()` (property) | Returns the real `logging.Logger` for this module |
| `level()` (property) | Gets/sets underlying logger level |
| `level(value)` (setter) | Gets/sets underlying logger level |
| `setLevel(level)` | Sets underlying logger level |
| `addHandler(hdlr)` | Adds a handler to the underlying logger |
| `removeHandler(hdlr)` | Removes a handler from the underlying logger |
| `log(level_name, message)` | Interpolates args and delegates to `SharedLogger.log(...)` |
| `debug(message)` | Logs at DEBUG level |
| `info(message)` | Logs at INFO level |
| `warning(message)` | Logs at WARNING level |
| `error(message)` | Logs at ERROR level |
| `exception(message)` | Logs at ERROR level (for exceptions) |
| `critical(message)` | Logs at CRITICAL level |

### Class `SharedLogger`

> Centralized backend logger and task log router

| Name | Description |
|---|---|
| `install_root_filter()` (classmethod) | Adds the dynamic module filter to the root logger |
| `set_name_filters(exact_names, prefixes)` (classmethod) | Sets allowed exact names and prefix-based module filters |
| `clear_name_filters()` (classmethod) | Clears all module name filters |
| `set_frontend_enabled(enabled)` (classmethod) | Enables/disables frontend (task buffer + SSE) logging |
| `set_frontend_level(level_name)` (classmethod) | Sets the minimum level for frontend output |
| `should_emit(module_name)` (classmethod) | Checks whether a module name passes current name filters |
| `get_logger(module_name)` (classmethod) | Installs root filter and returns a `ModuleLogger` |
| `register_task_buffer(task_id, lines)` (classmethod) | Delegates to `_TaskOutput.register_buffer(...)` |
| `unregister_task_buffer(task_id)` (classmethod) | Delegates to `_TaskOutput.unregister_buffer(...)` |
| `task_context(task_id)` (classmethod) | Context manager delegating to `_TaskOutput.context(...)` |
| `current_task_id()` (classmethod) | Delegates to `_TaskOutput.current_task_id()` |
| `format_message(message, start_timer)` (classmethod) | Appends caller name and elapsed time to message |
| `format_task_line(module_name, level_name, message)` (classmethod) | Formats a task output line as `"LEVEL MODULE - message"` |
| `log(module_name, level_name, message, start_timer, task_id)` (classmethod) | Main log method: filters, formats, logs via Python logger, writes to frontend |
| `_normalize_level(level_name)` (staticmethod) | Converts a level name string to `logging` int constant |

### Class `CustomFormatter` (logging.Formatter)

> Custom formatter to trim level names, module names, function names, and messages

| Name | Description |
|---|---|
| `__init__(fmt, datefmt, trim_level_len, trim_module_len, trim_func_len, trim_msg_len)` | Stores trimming parameters |
| `format(record)` | Trims levelname, name, funcName, message; formats; restores originals |

---

## `core/utilities/concurrency.py`

### Module-level functions

| Name | Description |
|---|---|
| `parallel_batch(fn, items)` | Executes `fn(*item)` for each item sequentially in a batch |
| `parallel_for(fn, items)` | Executes `fn(*item)` across a `ThreadPoolExecutor` with optional batching and progress bar |

---

## `core/utilities/helpers.py`

### Module-level functions

| Name | Description |
|---|---|
| `remove_directory(directory_path)` | Recursively deletes a directory if it exists |
| `delete_full_vectors()` | Deletes the four full vector files, keeping the split directory intact |
| `remove_models()` | Deletes the models directory |
| `remove_derived_caches()` | Deletes only the named derived cache files, skipping missing ones |
| `export_image_batch(pil_images)` | Converts PIL images into a float32 batched tensor in [0, 1] |

---

## `core/utilities/tasks.py`

> Background task infrastructure shared across sections

> **Scheduled move (REORGANIZATION_PLAN §0.3):** `start_task`, `set_task_output`, `get_task_status`, and `cancel_task` are server-only orchestration used solely by `adapters/server/endpoints/`; they move to `adapters/server/tasks.py`.

### Module-level functions

| Name | Description |
|---|---|
| `_run_captured(task_id, fn)` | Runs a task function with stdout/stderr captured into its task buffer |
| `start_task(fn)` | Registers a task and runs it in a daemon thread, returning the task id and status |
| `set_task_output(task_id, data)` | Replaces the stored output dict for a task and logs the status change |
| `get_task_status(task_id, since)` | Returns the task output dict with new log lines since a timestamp, or None |
| `cancel_task(task_id)` | Marks a running task as cancelled and writes a cancellation message, returning success |

---

## `core/utilities/utils.py`

> Small shared utilities used across the project

> **Scheduled deletion (REORGANIZATION_PLAN §0.1):** the whole module is dead — `parse_custom_text` is a legacy feature moved into `_recursive_parse_json` (`core/io/serialization.py`), and `first_present` was replaced by `get_value_from_entry` (`domain/vectors/helpers.py`).

### Module-level functions

| Name | Description |
|---|---|
| `parse_custom_text(val)` | Parses a value into a dict, passing dicts through and literal-evaling strings |
| `first_present(d, keys, default)` | Returns the first non-None value among the given keys of a dict, else the default |

---

## `domain/analysis/attribute_analysis.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `AGE_LABELS` | Fixed age class labels |
| `GENDER_LABELS` | Fixed gender class labels |
| `RACE_LABELS` | Fixed race class labels |

### Class `FaceAttributeAnalyzer`

> Predicts perceived age, gender, and race from face images

| Name | Description |
|---|---|
| `__init__(model_loader)` | Stores the model loader and initializes model, output dim, and processor state with a lock |
| `_ensure_loaded()` | Loads the HF vision model once under a lock when not already loaded |
| `predict(img)` | Returns the age, gender, and race distributions for a single image |
| `predict_batch(imgs)` | Runs the model over a batch and returns per-image softmax label distributions for age, gender, and race |

| Class constant | Description |
|---|---|
| `MODEL_KEY` | Constant model key used to load the face attribute model |

### Class `NSFWAnalyzer`

> Predicts NSFW probability for an image using a ViT classifier

| Name | Description |
|---|---|
| `__init__(model_loader)` | Stores the model loader and initializes NSFW model, output dim, and processor state |
| `_ensure_loaded()` | Loads the NSFW vision model when not already loaded |
| `predict(img)` | Returns the NSFW probability for a single image |
| `predict_batch(imgs)` | Returns the softmax NSFW-class probability for each image in the batch |

| Class constant | Description |
|---|---|
| `MODEL_KEY` | Constant model key used to load the NSFW model |

---

## `domain/analysis/helpers.py`

> Analysis helpers - utility functions for analysis endpoints

> **Scheduled move (REORGANIZATION_PLAN §0.4):** `distribute` is a pure stateless bucket-counting helper with zero domain knowledge, called only by `adapters/server/endpoints/analysis.py` (6 sites); it moves to `core/utilities/analysis.py`.

### Module-level functions

| Name | Description |
|---|---|
| `distribute(values, buckets)` | Counts values into named buckets by their first matching threshold |

---

## `domain/analysis/image_analysis.py`

### Module-level functions

| Name | Description |
|---|---|
| `process_single_batch(prepare_func, analyze_func, save_func, paths, data)` | Prepares, analyzes, and saves one batch of images, returning the analyzed entries |

### Module-level constants

| Symbol | Description |
|---|---|
| `REQUIRED_ANALYSIS_FIELDS` | Field names every analyzed entry must contain |
| `METRIC_KEYS` | Ordered names of the computed analysis metrics |

### Class `ImageAnalysis` (ImageVector)

| Name | Description |
|---|---|
| `__init__(raw_data, model_loader, batch_sizer)` | Initializes the mediapipe, face attribute, and NSFW analyzers and maps file ids to image paths |
| `_entry_has_required_fields(entry)` (staticmethod) | Returns whether an entry contains every required analysis field |
| `_entry_json_path(entry)` (staticmethod) | Derives the sidecar JSON path from the image path |
| `_save_entry_sidecar(entry)` | Atomically writes the entry JSON to its sidecar file when that file exists |
| `_image_size(img, entry, data)` | Records original and final size metrics into the entry unless already present |
| `_contrast(img, entry)` | Computes luminance standard deviation contrast into the entry unless present |
| `_sharpness(img, entry)` | Computes normalized Laplacian-variance sharpness into the entry unless present |
| `_noise_score(img, entry)` | Computes the normalized residual noise score into the entry unless present |
| `_colorfulness(img, entry)` | Computes Hasler-Susstrunk colorfulness normalized by the maximum into the entry unless present |
| `_artifact_score(img, entry)` | Estimates grid-aligned artifact magnitude into the entry unless present |
| `_edge_density(img, entry)` | Computes mean gradient magnitude edge density into the entry unless present |
| `_texture_lbp(img, entry)` | Computes LBP-histogram entropy as a texture score into the entry unless present |
| `_mediapipe_analysis(img, entry)` | Runs MediaPipe face and pose detection and merges results into the entry unless present |
| `_assemble_analysis_map(entry)` | Moves the metric keys into the analysis sub-map of the entry unless present |
| `_nsfw_analysis(img, entry)` | Adds the predicted NSFW score to the entry unless present |
| `_run_face_pass(entries)` | Predicts age, gender, and race for entries missing them and saves their sidecars |
| `_run_nsfw_pass(entries)` | Predicts NSFW scores for entries missing them and saves their sidecars |
| `analyze_image_batch(image_batch, data_batch)` | Runs every metric analyzer over the image batch and updates the matching entries |
| `_normalize_lora(entry)` (staticmethod) | Folds the legacy scalar lora_weight into a normalized weighted lora map |
| `analyze_images_from_paths(batch_size, max_workers)` | Analyzes all pending images in parallel batches with face and NSFW passes and caches the results |

---

## `domain/analysis/mediapipe_analysis.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `POSE_LANDMARK_NAMES` | Names of the 33 pose landmark points |

### Class `MediaPipeAnalyzer`

> Detects faces and body pose using MediaPipe

| Name | Description |
|---|---|
| `__init__()` | Initializes lazily-loaded face detector and pose landmarker references |
| `_image_to_rgb(img)` | Converts a PIL image to an RGB numpy array |
| `_get_face_detector()` | Lazily creates the MediaPipe face detector from the configured model path |
| `_get_pose_landmarker()` | Lazily creates the MediaPipe pose landmarker from the configured model path |
| `analyze(img)` | Detects faces and pose landmarks and returns relative-coordinate boxes and keypoints |

---

## `domain/analysis/trueskill.py`

### Module-level functions

| Name | Description |
|---|---|
| `normal_cumulative_distribution(x)` | Returns the standard normal cumulative distribution at x |
| `_clamp_uncertainty(uncertainty)` | Returns the uncertainty floored at epsilon |
| `expected_win_probability(first_rating, second_rating)` | Returns the probability that the first rating beats the second |
| `public_score_from_rating(rating)` | Converts a rating into a public score against a fresh initial rating |
| `normal_probability_density(x)` | Returns the standard normal probability density at x |
| `_add_dynamics_noise(uncertainty)` | Adds dynamics noise in quadrature to the uncertainty |
| `update_ratings(winner, loser)` | Returns updated ratings after the winner and loser of a comparison |
| `replay_ratings(rows)` | Replays comparison rows in id order and returns per-filename ratings and comparison counts |
| `rating_from_row(row)` | Builds a Rating from a row's rating_mu and rating_sigma values |

### Module-level constants

| Symbol | Description |
|---|---|
| `INITIAL_MEAN` | Initial TrueSkill skill mean (25.0) |
| `INITIAL_UNCERTAINTY` | Initial TrueSkill uncertainty (mean / 3) |
| `PERFORMANCE_VARIATION` | Game-to-game performance variation (mean / 6) |
| `DYNAMICS_NOISE` | Dynamics noise added per game (mean / 300) |
| `EPSILON` | Minimum uncertainty floor |
| `SCORE_STEEPNESS` | Slope mapping rating differences to public scores, from ranking config |

### Class `Rating`

| Field | Description |
|---|---|
| `mu_skill` | Rating's skill mean |
| `sigma_uncertainty` | Rating's uncertainty |

---

## `domain/comparison/algorithm/graph_helpers.py`

> Reusable graph-query helpers for the ranking algorithm

> **Scheduled deletion (REORGANIZATION_PLAN §0.1):** `get_chain_length`, `group_nodes_by_extreme`, and `find_lowest_confidence_images` are dead — module-level helpers never imported.

### Module-level functions

| Name | Description |
|---|---|
| `is_top_node(node, cg)` | Returns True if the node has no better-than links |
| `is_bottom_node(node, cg)` | Returns True if the node has no worse-than links |
| `get_node_component(node, cg)` | Returns the component id of the node, or None |
| `get_component_members(comp_id, cg)` | Returns the member filename list for a component id |
| `get_chain_length(node, cg)` | Returns the chain-length metric for the node |
| `group_nodes_by_extreme(nodes, cg)` | Groups nodes into top-by-component and bottom-by-component dicts |
| `is_collapsable_pair(filename_a, filename_b, cg)` | Returns True when both nodes are same-component extremes not sharing a path |
| `filter_excluded_images(images, exclude_set)` | Removes images whose filename is in the exclude set |
| `find_lowest_confidence_images(images)` | Selects a diverse subset of high-uncertainty images for fallback pairing |

### Class `CrystalGraph` (Protocol)

| Name | Description |
|---|---|
| `get_node(node_id)` | Returns the graph node for a node id or None |
| `get_all_nodes(only_top, only_bottom)` | Returns all graph nodes, optionally only top or bottom nodes |
| `get_component(node_id, component_id, chain_id)` | Returns the component for a node, component, or chain id |
| `get_all_components()` | Returns all graph components |
| `get_all_chains(min_length, sort_order)` | Returns all chains optionally filtered by minimum length and sort order |
| `get_graph_stats()` | Returns aggregate graph statistics |
| `are_in_same_path(img1, img2)` | Returns whether two images lie on the same chain path |
| `get_main_chain_member_count(chain_id)` | Returns the member count of the main chain for a chain id |

---

## `domain/comparison/algorithm/merge_sort_ranker.py`

> Public orchestration layer for step01 pair selection and comparison recording

### Module-level functions

| Name | Description |
|---|---|
| `select_pair_for_comparison(exclude_set, crystal_graph, comparison_repo, all_images)` | Selects the next pair of images to compare with its phase index, rebuilding the graph when stale |

### Class `CrystalGraph` (Protocol)

| Name | Description |
|---|---|
| `is_cache_stale()` | Returns whether the graph cache is stale |
| `rebuild_from_database(images, comparisons)` | Rebuilds the graph from images and comparisons data |
| `get_node(node_id)` | Returns the graph node for a node id or None |
| `get_all_chains(min_length, sort_order)` | Returns all chains optionally filtered by minimum length and sort order |
| `get_all_nodes(only_top, only_bottom)` | Returns all graph nodes, optionally only top or bottom nodes |
| `get_graph_stats()` | Returns aggregate graph statistics |
| `are_in_same_path(img1, img2)` | Returns whether two images lie on the same chain path |
| `get_main_chain_member_count(chain_id)` | Returns the member count of the main chain for a chain id |

---

## `domain/comparison/algorithm/pair_active.py`

> Active pair selection for the TrueSkill-based step01 flow

### Module-level functions

| Name | Description |
|---|---|
| `stable_seed_pool(images)` | Returns the top seed filenames by comparison count using the configured percentage |
| `_pair_key(filename_a, filename_b)` | Returns a canonical sorted tuple for a filename pair |
| `existing_pairs(comparison_repo)` | Returns the set of already-recorded pair keys from the repository |
| `_component_id(filename, cg)` | Returns the component id for a filename, or None |
| `_score_gap(image_a, image_b)` | Returns the absolute score difference between two images |
| `_find_unseen_candidates(source, candidates, pair_set)` | Yields candidates that are not already paired with the source |
| `_are_in_different_paths(filename_a, filename_b, cg)` | Returns True when the two filenames are not on the same graph path |
| `_build_low_count_pool(candidate_images)` | Selects the images with the fewest comparisons until the pool is large enough |
| `phase_seed_coverage(seed_candidates, existing_pair_set, cg, comparison_repo)` | Returns an unseen seed-phase pair for an under-target seed image, or None |
| `phase_anchor_insert(candidate_images, seed_pool, existing_pair_set, cg, comparison_repo)` | Pairs the lowest-comparison candidate with the closest-mu image on a different path, or None |
| `phase_collapsible_pairs(candidate_images, pair_set, cg, comparison_repo)` | Returns two same-component tops or bottoms to resolve collapsible branches, or None |
| `phase_chain_merge(candidate_images, cg, comparison_repo)` | Returns a close-scoring cross-chain mid-node pair from the shortest chains, or None |
| `phase_uncertainty_refine(candidate_images, pair_set, cg, comparison_repo)` | Pairs the highest-sigma candidate with the closest-mu seed image, or None |
| `phase_fallback(candidate_images, pair_set, cg, comparison_repo)` | Returns the first unseen pair in comparison-count order, or None |

### Class `ComparisonRepository` (Protocol)

| Name | Description |
|---|---|
| `get_all_comparisons(weight)` | Returns all comparisons, optionally filtered by weight |
| `get_images_with_only_wins()` | Returns filenames that have only wins |
| `get_images_with_only_losses()` | Returns filenames that have only losses |

### Class `CrystalGraph` (Protocol)

| Name | Description |
|---|---|
| `get_node(node_id)` | Returns the graph node for a node id or None |
| `get_all_nodes(only_top, only_bottom)` | Returns all graph nodes, optionally only top or bottom nodes |
| `get_component(node_id, component_id, chain_id)` | Returns the component for a node, component, or chain id |
| `get_all_chains(min_length, sort_order)` | Returns all chains optionally filtered by minimum length and sort order |
| `get_graph_stats()` | Returns aggregate graph statistics |
| `are_in_same_path(img1, img2)` | Returns whether two images lie on the same chain path |

---

## `domain/comparison/algorithm/phase_order.py`

> Phase ordering configuration

### Module-level functions

| Name | Description |
|---|---|
| `reset_skip()` | Resets the phase skipping index to zero |
| `get_phases()` | Returns a JSON-serializable version of PHASES with callables stripped and names added |
| `select_pair(all_images, candidate_images, cg, comparison_repo)` | Runs each phase in order and returns the first pair found with its phase index |

### Module-level constants

| Symbol | Description |
|---|---|
| `PHASES` | Ordered list of (name, callable) pairing phases run by select_pair |

---

## `domain/comparison/algorithm/view.py`

> Read-only serialization of graph objects into comparison-frontend payloads

### Module-level functions

| Name | Description |
|---|---|
| `_describe_one(node, cg)` | Builds the per-image payload from a NodeProxy |
| `describe_image(node, cg)` | Returns all per-image info for a single node |
| `describe_pair(node_a, node_b, phase_index, cg)` | Returns phase-specific pair context built from the two nodes and config |

---

## `domain/comparison/comparison_recorder.py`

> Comparison recording and rating updates

### Module-level functions

| Name | Description |
|---|---|
| `update_scores_after_comparison(winner_filename, loser_filename, winner_data, loser_data, impact_factor)` | Updates TrueSkill ratings, public scores, and comparison counts for winner and loser data |

### Class `ComparisonRepository` (Protocol)

| Name | Description |
|---|---|
| `add_comparison(filename_a, filename_b, winner, weight, transitive_depth, timestamp)` | Adds a comparison row and returns its id or None |
| `comparison_exists_for_pair(filename_a, filename_b)` | Returns whether a comparison already exists for the given pair |
| `get_all_comparisons()` | Returns all recorded comparisons |

### Class `ImageRepository` (Protocol)

| Name | Description |
|---|---|
| `get_image(filename)` | Returns the image record for a filename or None |
| `update_image_rating_state(filename, score, rating_mu, rating_sigma, comparison_count, touch_timestamp)` | Persists the rating state for an image, optionally touching its timestamp |

### Class `PathSyncer` (Protocol)

| Name | Description |
|---|---|
| `sync_image_metadata_to_json(filename, score, rating_mu, rating_sigma, comparison_count, all_comparisons)` | Syncs image metadata to its sidecar JSON, optionally with all comparisons |

### Class `GraphService` (Protocol)

| Name | Description |
|---|---|
| `apply_comparison(winner, loser)` | Applies a comparison between winner and loser to the ranking graph |

### Class `ComparisonRecorder`

| Name | Description |
|---|---|
| `__init__(comparison_repo, image_repo, path_syncer, graph_service)` | Stores the comparison, image, path-syncer, and graph dependencies |
| `_persist_image_state(filename, data)` | Persists the rating state of one filename through the image repository |
| `record_comparison(filename_a, filename_b, winner, impact_factor, transitive_depth)` | Records one comparison, updates both image ratings, syncs JSON sidecars, and applies it to the graph |

---

## `domain/comparison/state.py`

> Centralised mutable state for the ranking algorithm

### Module-level functions

| Name | Description |
|---|---|
| `get_cached_all_images(images)` | Returns the cached all-images list, refreshing from the repository when stale |
| `get_cached_image(filename, images)` | Returns the image with the given filename from the cache or supplied list, or None |
| `invalidate_images_cache()` | Resets the cached images data and timestamp |

---

## `domain/data_transformation/data_transformer.py`

### Module-level functions

| Name | Description |
|---|---|
| `get_feature_mapping_from_config()` | Builds index-to-vector and vector-range maps from the vector config |
| `_label_position_slot(pos_in_unit)` | Labels a per-unit position slot by its coordinate name |
| `_label_keypoint_slot(vec_name, pos_in_unit)` | Labels a per-unit keypoint slot with vector name and coordinate |
| `_label_person_map_slot(vec_name, pos_in_unit)` | Labels a per-unit person-map slot from the saved map JSON |
| `_load_map_slots(vec_name)` | Loads the saved map JSON slot labels for a map-type vector, or None |
| `_print_vector_summary(vec_name, vec_type, kept_in_vec, total_in_vec, slot_size, per_unit_size, start_idx)` | Prints one vector line, expanding multi-slot and map vectors by sub-feature |
| `list_filtered_features(transformer)` | Prints a per-vector summary of which features survived the gain-based pruning |

### Class `DataTransformer`

| Name | Description |
|---|---|
| `__init__(training_loader, model_trainer)` | Stores the training loader and trainer and builds the feature mapping |
| `get_raw_data()` | Returns aligned vectors and scores arrays keyed by shared order |
| `filter_low_comparisons(threshold)` | Keeps filenames with at least the threshold comparisons, replays their ratings, and caches the rule |
| `filter_unused_features(vectors_keyed, scores_keyed, steps, verbose)` | Trains a fast LightGBM model and returns the kept feature indices, cached as the feature rule |
| `calculate_interaction_batch(X_batch, y_batch, n_features_in, accumulators)` | Accumulates correlation sums for the interaction features of a batch |
| `compute_correlations(k, accumulators, n_samples, dtype)` | Computes per-interaction F-scores and returns the top-k indices and an empty matrix |
| `build_interaction_batch(X_batch, top_k_indices_local, n_features_in)` | Extracts the selected interaction columns for a batch |
| `add_interaction_features(x, y, target_k)` | Generates and selects the top-k interaction features, appending them to X, with caching |
| `apply_feature_filter(vecs)` | Applies the cached kept-indices rule to each vector |
| `apply_interaction_features(vecs)` | Appends the cached selected interaction features to the input vectors |

| Class constant | Description |
|---|---|
| `poly` | Class-level PolynomialFeatures instance used to generate interaction features |

---

## `domain/database/ports/__init__.py`

| Name | Description |
|---|---|
| `__all__` | Exports ['ImageRepository', 'ComparisonRepository', 'PathResolver'] |
| `ComparisonRepository` | Re-exported from `.repository_ports` (see below) |
| `ImageRepository` | Re-exported from `.repository_ports` (see below) |
| `PathResolver` | Re-exported from `.repository_ports` (see below) |

---

## `domain/database/ports/repository_ports.py`

> Repository interface ports for domain isolation

### Class `ImageRepository` (Protocol)

| Name | Description |
|---|---|
| `get_image(filename)` | Returns image data dict or `None` |
| `get_all_images()` | Returns list of all image data dicts |
| `add_image(filename, score, comparison_count, prompt_tags, rating_mu, rating_sigma)` | Inserts an image record |
| `update_image_rating_state(filename, score, rating_mu, rating_sigma, comparison_count)` | Updates rating fields for an image |

### Class `ComparisonRepository` (Protocol)

| Name | Description |
|---|---|
| `add_comparison(filename_a, filename_b, winner, impact_factor, phase)` | Inserts a comparison record |
| `get_all_comparisons()` | Returns all comparison records |
| `get_total_comparisons()` | Returns total comparison count |
| `comparison_exists_for_pair(filename_a, filename_b)` | Checks existence of a comparison |

### Class `PathResolver` (Protocol)

| Name | Description |
|---|---|
| `sync_image_metadata_to_json(filename)` | Syncs image metadata to a JSON sidecar file |

---

## `domain/graph/chain_manager.py`

### Module-level functions

| Name | Description |
|---|---|
| `parse_comparison(comp)` | Extracts `filename_a`, `filename_b`, `winner`, `loser` from comparison dict |
| `add_directed_edge(better_than, worse_than, winner, loser)` | Adds a directed edge from loser to winner |
| `add_undirected_edge(adjacency, filenames, filename_a, filename_b)` | Adds an undirected edge between two filenames |
| `process_one_comparison(comp, better_than, worse_than, adjacency, filenames)` | Processes a single comparison: parses, adds directed and undirected edges |
| `has_no_predecessors(node, better_than)` | Returns True if node has no incoming (better-than) edges |
| `has_no_successors(node, worse_than)` | Returns True if node has no outgoing (worse-than) edges |
| `find_top_nodes(all_filenames, better_than)` | Returns set of nodes with no predecessors |
| `find_bottom_nodes(all_filenames, worse_than)` | Returns set of nodes with no successors |
| `bfs_one_component(start, adjacency, visited)` | BFS traversal to find all nodes in one connected component |
| `index_component(members, comp_id, node_component, component_members)` | Indexes all members of a component into the component lookups |
| `build_components(all_filenames, adjacency)` | Builds all connected components from the undirected adjacency graph |
| `same_component(u, v, node_component)` | Checks whether two nodes are in the same component |
| `find_common_chain_id(node_chains, other_chains)` | Finds a chain ID present in both node chain mappings |
| `tarjan_scc(nodes, successors)` | Tarjan's algorithm to find strongly connected components; contains nested `strongconnect(v)` |

### Class `ChainManager`

| Name | Description |
|---|---|
| `__init__()` | Initialises all internal graph data structures (empty) |
| `get_all_filenames()` | Returns set of all filenames in the graph |
| `get_top_nodes()` | Returns list of top (no-predecessor) nodes |
| `get_bottom_nodes()` | Returns list of bottom (no-successor) nodes |
| `get_better_than(node_id)` | Returns list of nodes better than (predecessors of) the given node |
| `get_worse_than(node_id)` | Returns list of nodes worse than (successors of) the given node |
| `is_top(node_id)` | Checks if a node is a top node |
| `is_bottom(node_id)` | Checks if a node is a bottom node |
| `get_component_id(node_id)` | Returns the connected component ID for a node |
| `get_component_members(comp_id)` | Returns filenames in a component by component ID |
| `get_component_count()` | Returns total number of connected components |
| `get_built_at()` | Returns the timestamp the graph was built |
| `set_built_at(dt)` | Stores the build timestamp |
| `get_db_comparison_count()` | Returns the DB comparison count snapshot |
| `set_db_comparison_count(count)` | Stores the DB comparison count snapshot |
| `build(comparisons, all_filenames)` | Full rebuild: resets adjacency, builds from comparisons, identifies tops/bottoms, builds components and chains |
| `_reset_adjacency()` | Clears all directed/undirected adjacency structures |
| `_build_from_comparisons(comparisons)` | Iterates comparisons and adds edges |
| `apply_comparison(winner, loser)` | Incremental update: adds a single comparison edge, updates top/bottom, merges components |
| `_remove_from_bottom_if_not_anymore(winner)` | Removes winner from bottom if it now has outgoing edges |
| `_remove_from_top_if_not_anymore(loser)` | Removes loser from top if it now has incoming edges |
| `_add_to_bottom_if_needed(loser)` | Adds loser to bottom if it has no outgoing edges |
| `_add_to_top_if_needed(winner)` | Adds winner to top if it has no incoming edges |
| `_update_top_bottom_for_edge(winner, loser)` | Updates top/bottom sets after adding a new edge |
| `_component_of(node)` | Returns component ID for a node |
| `_both_have_components_and_different(cw, cl)` | Returns True if both nodes have components and they differ |
| `_neither_has_component(cw, cl)` | Returns True if neither node has a component |
| `_winner_lacks_component(cw, cl)` | Returns True if winner has no component but loser does |
| `_loser_lacks_component(cw, cl)` | Returns True if loser has no component but winner does |
| `_create_new_component(winner, loser)` | Creates a new component containing both winner and loser |
| `_add_winner_to_loser_component(winner, cl)` | Adds winner to loser's existing component |
| `_add_loser_to_winner_component(loser, cw)` | Adds loser to winner's existing component |
| `_merge_node_components(winner, loser)` | Merges or creates components for a newly connected pair |
| `_ensure_larger_component_kept(keep_id, remove_id)` | Returns IDs swapped so the larger component is kept |
| `_reassign_nodes(remove_id, keep_id)` | Reassigns all nodes from the removed component to the kept one |
| `_absorb_removed_component(keep_id, remove_id)` | Merges member lists from remove_id into keep_id and deletes remove_id |
| `_merge_components(keep_id, remove_id)` | Merges two components, keeping the larger one |
| `_identify_top_bottom()` | Populates top and bottom node sets via helper functions |
| `_build_components()` | Populates component structures via `build_components` |
| `_dedup_path(path)` (staticmethod) | Deduplicates a path by stopping at first repeated element |
| `_build_chains()` | Builds chains using forward/backward DP on SCC-condensed DAG |
| `get_chains()` | Returns dict of all `{chain_id: [node_list]}` pairs |
| `get_node_chains(node_id)` | Returns all `(chain_id, chain_list)` pairs for a node |
| `get_node_main_chain(node_id)` | Returns the main `(chain_id, chain_list)` for a node |
| `get_min_chain_count()` | Returns the number of chains |
| `_quick_reject(start, end)` | Quick pre-checks for reachability (missing node, different component, no edges) |
| `_bfs_search(start, end, max_depth)` | BFS to find if `end` is reachable from `start` up to `max_depth` |
| `_can_reach(start, end)` | Checks reachability using quick reject, same-chain check, then BFS |
| `_check_same_chain(u, v)` | Returns `(same_chain, u_before_v)` for two nodes |

---

## `domain/graph/chain_proxy.py`

### Class `ChainProxy`

> Represents one directed path (chain). Created from min chain cover results

| Name | Description |
|---|---|
| `__init__(chain, chain_id, node_list)` | Stores chain manager, chain ID, node list |
| `id()` (property) | Returns chain ID integer |
| `nodes()` (property) | Returns list of `NodeProxy` for all nodes in this chain |
| `length()` (property) | Returns number of nodes in the chain |
| `is_main()` (property) | Returns `True` if any node has this chain as its main chain |
| `first()` (property) | Returns first `NodeProxy` in chain, or `None` |
| `last()` (property) | Returns last `NodeProxy` in chain, or `None` |
| `get_nodes(only_top, only_bottom)` | Returns filtered list of `NodeProxy` by top/bottom status |
| `node_position(node_id)` | Returns index of a node ID within the chain |
| `get_component()` | Returns `ComponentProxy` for the first node's component |
| `__repr__()` | Returns `ChainProxy(id=..., length=...)` |

---

## `domain/graph/component_proxy.py`

### Class `ComponentProxy`

> Represents one connected component

| Name | Description |
|---|---|
| `__init__(chain, comp_id)` | Stores chain manager and component ID |
| `id()` (property) | Returns component ID integer |
| `nodes()` (property) | Returns list of `NodeProxy` for all nodes in the component |
| `size()` (property) | Returns number of nodes in the component |
| `get_chains(minimal_required)` | Returns all `ChainProxy` objects whose chains intersect this component |
| `__repr__()` | Returns `ComponentProxy(id=..., size=...)` |

---

## `domain/graph/node_proxy.py`

### Class `NodeProxy`

> Represents one image/node in the graph. Created on demand, zero overhead

| Name | Description |
|---|---|
| `__init__(chain, node_id, image_data)` | Stores chain manager, node ID, optional image data |
| `id()` (property) | Returns the node ID string |
| `filename()` (property) | Returns the node ID (aliased as filename) |
| `score()` (property) | Returns image score, defaulting to `0.5` |
| `mu_skill()` (property) | Returns rating mu, defaulting to `25.0` |
| `sigma_uncertainty()` (property) | Returns rating sigma, defaulting to `25.0/3.0` |
| `comparison_count()` (property) | Returns comparison count, defaulting to `0` |
| `chain_count()` (property) | Returns number of chains this node appears in |
| `main_chain_in_chains()` (property) | Returns whether the node's main chain ID is in its chain list |
| `prompt_tags()` (property) | Returns prompt tags string or `None` |
| `last_compared_at()` (property) | Returns last comparison timestamp string or `None` |
| `is_top()` | Delegates to chain manager to check if node is a top node |
| `is_bottom()` | Delegates to chain manager to check if node is a bottom node |
| `get_links(better_than, worse_than)` | Returns unique `NodeProxy` objects linked to this node, filtered by direction |
| `get_chain(only_main)` | Returns `ChainProxy` objects for the node's main chain or all chains |
| `get_position_in_chain()` | Returns the node's index within its main chain |
| `get_component()` | Returns `ComponentProxy` for the node's connected component |
| `__repr__()` | Returns `NodeProxy(<node_id>)` |

---

## `domain/graph/tests/test_chain_manager.py`

> Check that bottom nodes are the last element in their main chain

### Module-level functions

| Name | Description |
|---|---|
| `test_bottom_nodes_are_chain_last()` | Asserts all chains start at top nodes and end at bottom nodes against real DB |
| `test_performance_on_large_chains()` | Tests ChainManager processes a large dataset in under 30 seconds |
| `test_cycles_do_not_prevent_bottom_reachability()` | Verifies cyclic paths still reach and end at the absolute bottom node |
| `test_transitive_reduction_sorting()` | Verifies `a>b, b>c, a>c` builds a single sorted chain `a>b>c` |
| `test_uncompared_nodes_are_isolated_top_bottom()` | Tests uncompared images form single-node chains acting as both top and bottom |
| `test_top_bottom_match_database_exactly()` | Asserts computed top/bottom sets exactly match DB "only-wins" and "only-losses" |
| `test_chain_snapshot_matches_known_optimal()` | Verifies exact chain output for a manually designed DAG |

### Module-level constants

| Symbol | Description |
|---|---|
| `DATASET_SIZE` | Number of images in the synthetic large-dataset performance test |

---

## `domain/training/calibration.py`

### Module-level functions

| Name | Description |
|---|---|
| `_as_1d_float_array(values)` | Flattens values into a float32 array with non-finite entries removed |
| `_strictly_increasing(values)` | Adjusts an array so each value is finite and strictly greater than the previous |
| `build_score_calibration(raw_scores, target_scores, num_points)` | Builds a monotonic quantile-based score calibration table, or None for empty input |
| `extract_score_calibration(data)` | Extracts the score_calibration dict from the data, or None |
| `apply_score_calibration(raw_scores, calibration)` | Maps raw scores through the calibration tables, or returns them unchanged |

---

## `domain/training/matrix_analysis.py`

> 2D Matrix Analysis for Text Data Parameters

### Class `MatrixAnalyzer`

| Name | Description |
|---|---|
| `__init__(scores, text_data, memory_limit)` | Stores scores and text data and initializes parameter bookkeeping structures |
| `get_text_weight(original_text)` (staticmethod) | Splits a text:weight string into normalized text and a float weight |
| `_extract_all_params_from_record(record)` | Extracts normalized parameter strings from a record, including lora entries |
| `_add_param_from_value(key, value, params, prefix)` | Appends normalized parameter strings for a key-value pair to the params list |
| `build_matrix()` | Builds the parameter id maps and co-occurrence score matrix from all records |
| `calculate_statistics(min_count)` | Computes per-cell score statistics with polars and stores them in cell_stats |
| `export_to_json(output_path)` | Writes the cell statistics to a JSONL file |
| `print_top_correlations(top_n)` | Prints the top-N cells by mean score |
| `get_matrix_size()` | Returns the parameter matrix dimensions |
| `get_matrix_summary()` | Returns aggregate summary statistics for the matrix |

---

## `domain/training/parameter_analysis.py`

> Parameter Analysis Module

### Module-level functions

| Name | Description |
|---|---|
| `main()` | Loads vectors and text data and runs the standalone parameter analysis |

### Module-level constants

| Symbol | Description |
|---|---|
| `SKLEARN_AVAILABLE` | Whether sklearn is importable |
| `MATPLOTLIB_AVAILABLE` | Whether matplotlib is importable |

### Class `ParameterAnalyzer`

| Name | Description |
|---|---|
| `__init__(vectors_data, text_data, output_dir)` | Stores vectors and text data, creates the output directory, and builds the score array |
| `analyze_all()` | Runs parameter pair analysis, term correlations, and report generation |
| `analyze_parameter_pairs()` | Creates scatter plots and category stats for steps, cfg, lora, sampler, and scheduler |
| `analyze_term_correlations()` | Computes per-term score statistics and saves top and bottom terms to JSON |
| `_create_scatter(x, y, colors, name, xlabel, ylabel, normalize)` | Saves a scatter plot of x vs y colored by score, optionally normalized |
| `_create_2d_scatter(x, y, colors, name, xlabel, ylabel, zlabel)` | Saves a 2D scatter plot colored by score with a correlation annotation |
| `_get_category_scores(categories)` | Maps category names to their aligned score lists |
| `_save_category_stats(filename, category_scores)` | Writes per-category mean, std, count, max, and min stats to JSON |
| `generate_report()` | Writes a markdown report of the score summary statistics |

---

## `domain/training/plot.py`

### Class `PlotManager`

> Manages all plotting functionality for model training and analysis

| Name | Description |
|---|---|
| `_get_metric_direction(objective, metric)` (staticmethod) | Returns whether higher is better for the objective's metric |
| `_prepare_finite_data(y, preds)` (staticmethod) | Filters y and preds to finite pairs |
| `_calculate_scatter_sizes(counts, min_size_px, max_size_px, power)` (staticmethod) | Maps point counts to pixel sizes with power scaling |
| `_setup_scatter_axes(ax, y_min, y_max)` (staticmethod) | Draws the perfect-prediction diagonal and sets equal axes limits |
| `plot_scatter_comparison(y_plot, p_plot, plot, min_size_px, max_size_px, power, label_threshold, title, x_label, y_label)` (staticmethod) | Plots a sized scatter of actual vs predicted with count labels |
| `plot_scatter_comparison_continuous(y_plot, p_plot, plot, min_size_px, max_size_px, power, label_threshold, title, x_label, y_label, save_path=None, show=True)` (staticmethod) | Plots a scatter of actual vs predicted with value labels, optionally saving to `save_path` |
| `prepare_plot_data(y, preds)` (staticmethod) | Returns the finite sample pairs to plot |
| `print_comparison_metrics(y, preds, metrics, objective, calibrated)` (staticmethod) | Prints sample and stored R2 and pairwise accuracy metrics |
| `compare_model_vs_data(x, y, plot, limit=100, save_path=None, show=True)` (staticmethod) | Samples data, predicts with the trained model, calibrates ranking scores, and plots the comparison, optionally saving to `save_path` |
| `_plot_metric_on_axes(ax, metric_name, values, label, direction_higher)` (staticmethod) | Plots one metric series with a direction annotation on the axis |
| `plot_metric(axes, current_metric, label)` (staticmethod) | Plots each current metric series on the given axes |
| `plot_loss_curve(result_metrics=None, save_path=None, show=True)` (staticmethod) | Plots the validation curves from result metrics or saved diagnostics, optionally saving to `save_path` |
| `plot_score_distribution(y, save_path=None, show=True)` (staticmethod) | Plots the score distribution as binned bars over the [0, 1] score range, optionally saving to `save_path` |
| `plot_continuous_analysis(data_dict, group_name, x_label, y_label, cols, share_axes)` (staticmethod) | Plots a grid of scatter subplots for continuous point groups |
| `plot_discrete_analysis(data_dict, group_name, x_label, y_label, cols)` (staticmethod) | Plots a grid of scatter subplots for discrete value groups |
| `plot_aggregate_summary(data_dict, group_name, value_label, top_percent, limit, ascending)` (staticmethod) | Plots a bar chart of group means with error bars for the most-used groups |
| `plot_individual_metrics(data_dict, cols, bins)` (staticmethod) | Plots binned bar charts of score means and std per setting value |
| `plot_discrete_object_analysis(discrete_data, title_prefix, cols)` (staticmethod) | Plots per-metric bar charts of category means with sample counts |
| `prepare_face_data(text_data, scores)` (staticmethod) | Builds face logit and bbox dataframes and detection-presence score lists |
| `plot_face_bbox(df_bbox)` (staticmethod) | Plots face position and width/height vs score scatter charts |
| `plot_positional_data(pos_data, group_name, cols, invert_y)` (staticmethod) | Plots per-name position scatter grids colored by score |
| `plot_positional_bbox(pos_data, group_name, cols, invert_y, alpha)` (staticmethod) | Plots per-name bounding-box rectangles colored by score |
| `plot_detection_presence(pose_score, no_pose_score, lh_score, no_lh_score, rh_score, no_rh_score, n)` (staticmethod) | Plots detected vs not-detected score boxplots with Mann-Whitney p-values |
| `__init__(save_path, frequency, status_bar)` | Initializes save path, history, frequency, and status bar |
| `__call__(env)` | Appends evaluation results to history and periodically plots the final results |
| `plot_final_results()` | Plots the accumulated valid metric curves and saves them to the save path |

---

## `domain/vectors/embedding_vector.py`

### Class `EmbeddingVector`

| Name | Description |
|---|---|
| `__init__(name, slot_size)` | Initializes name, slot size, and the value, vector, and text lists |
| `parse_value_list(entries, alias)` | Extracts string values from entries by name or alias into the value list |
| `create_vector_batch(current_batch)` | Encodes a batch of text values into L2-normalized embedding vectors |
| `create_vector_list(batch_size)` | Encodes all values in batches into the vector list |
| `create_text_batch(current_batch)` | Copies a batch of id and text pairs into a dict |
| `create_text_list(batch_size)` | Copies all values in batches into the text list |

---

## `domain/vectors/helpers.py`

### Module-level functions

| Name | Description |
|---|---|
| `l2_normalize_batch(vectors)` | L2-normalizes each row of the vector batch |
| `get_value_from_entry(entry, name, alias)` | Looks up a value from an entry by name or first matching alias |

---

## `domain/vectors/image_vector.py`

### Class `ImageVector`

| Name | Description |
|---|---|
| `__init__(name, model_key, slot_size)` | Initializes image, path, and vector state along with the batch sizer and size config |
| `array_to_pil(arr)` | Converts numpy image arrays into RGB PIL images |
| `prepare_image_batch(image)` | Converts various image inputs into a list of RGB PIL images |
| `create_image_vector_batch(current_batch)` | Encodes a same-size batch of images into L2-normalized vectors |
| `get_batch_size(width, height, rebuild, bound=None)` | Returns the recommended batch size for the given dimensions, bounded by bound when given |
| `create_vector_list(entries, rebuild)` | Loads the vision model and encodes all entries in batches |
| `create_vector_list_from_paths(entries)` | Encodes images bucketed by exact size with memory-controlled batch sizes, permanently capping batch size on CUDA OOM |

---

## `domain/vectors/keypoint_vector.py`

### Class `KeypointVector`

> Per-instance keypoint vector (e.g. body pose landmarks)

| Name | Description |
|---|---|
| `__init__(name)` | Initializes name, value and vector lists, and the vector config reference |
| `_config_index()` | Returns the config index for this vector's name |
| `_grow(needed)` | Grows the configured slot size when needed and persists the config |
| `parse_value_list(entries, add_new_values, alias)` | Stores raw per-instance keypoint dicts and grows the slot for the instance count |
| `create_vector_list()` | Flattens keypoint dicts into fixed-length padded vectors |

| Class constant | Description |
|---|---|
| `PER_UNIT` | Number of coordinates per keypoint instance |
| `KEYS` | Coordinate keys flattened per keypoint instance |

---

## `domain/vectors/map_vector.py`

### Class `MapVector`

> Categorical map with float weights

| Name | Description |
|---|---|
| `__init__(name)` | Initializes name, value and vector lists, and the vector config reference |
| `_config_index()` | Returns the config index for this vector's name |
| `_maybe_grow(size)` | Grows the configured slot size when needed |
| `_normalize(value)` | Converts any value shape into a weighted category dict |
| `parse_value_list(entries, add_new_values, alias)` | Normalizes entries and registers new categories in the maps list |
| `create_vector_list()` | Builds weighted one-hot vectors over the category vocabulary |

---

## `domain/vectors/number_vector.py`

### Class `IntVector`

| Name | Description |
|---|---|
| `__init__(name, max_normalization)` | Initializes name, max normalization, and value and vector lists |
| `parse_value_list(entries, alias)` | Extracts integer values from entries by name or alias |
| `create_vector_list()` | Clamps values to the max normalization into single-element vectors |

### Class `FloatVector`

| Name | Description |
|---|---|
| `__init__(name, max_normalization)` | Initializes name, max normalization, and value and vector lists |
| `parse_value_list(entries, alias)` | Extracts float values from entries by name or alias |
| `create_vector_list()` | Clamps values to the max normalization into single-element vectors |

---

## `domain/vectors/person_map_vector.py`

### Class `PersonMapVector`

> Per-person categorical map (e.g. age / gender / race)

| Name | Description |
|---|---|
| `__init__(name)` | Initializes name, value and vector lists, and the vector config reference |
| `_config_index()` | Returns the config index for this vector's name |
| `_per_unit()` | Returns the category count for this person map |
| `_grow(needed)` | Grows the configured slot size when needed and persists the config |
| `parse_value_list(entries, add_new_values, alias)` | Stores per-person category dicts, registers new categories, and grows the slot |
| `create_vector_list()` | Flattens per-person softmax blocks into fixed-length padded vectors |

---

## `domain/vectors/position_vector.py`

### Class `PositionVector`

> Per-instance positional vector (e.g. face bounding box)

| Name | Description |
|---|---|
| `__init__(name)` | Initializes name, value and vector lists, and the vector config reference |
| `_config_index()` | Returns the config index for this vector's name |
| `_grow(needed)` | Grows the configured slot size when needed and persists the config |
| `parse_value_list(entries, add_new_values, alias)` | Stores raw per-instance position dicts and grows the slot for the instance count |
| `create_vector_list()` | Flattens position dicts into fixed-length padded vectors |

| Class constant | Description |
|---|---|
| `PER_UNIT` | Number of coordinates per position instance |
| `KEYS` | Coordinate keys flattened per position instance |

---

## `domain/vectors/terms.py`

### Module-level functions

| Name | Description |
|---|---|
| `extract_weight_from_paren(text)` | Parses `(term:weight)` or `(term)` syntax, returning `(content, weight)` |
| `tokenize_by_depth(text, splitters)` | Splits text by splitters and parenthetical boundaries, respecting nesting depth |
| `clean_term(term)` | Normalizes string: lowercases, removes backslashes/pipes/punctuation/stray weight markers |
| `filter_terms(terms, connectors, splitters)` | Removes stopwords unless protected by connector/splitter sets |
| `deduplicate_terms(terms)` | Merges duplicate terms, keeping the highest weight |
| `_extract_recursive(text, current_weight, splitters)` | Recursively handles parentheses nesting and weight multiplication |
| `extract_terms(text, connectors, splitters)` | Main entry: recursively parses, cleans, filters, deduplicates prompt text into weighted terms |

### Class `ExtractionResult`

| Field | Description |
|---|---|
| `terms` | Final list of `(term, weight, index)` tuples |
| `raw` | Raw extracted terms before processing |
| `filtered_out` | Terms removed by stopword filtering |
| `stripped` | Terms that became empty after cleaning |
| `duplicates` | Terms removed by deduplication |

---

## `domain/vectors/tests/test_terms.py`

### Module-level functions

| Name | Description |
|---|---|
| `test_extract_terms_variations(input_text, expected_output)` | Parametrized test for `extract_terms` with various prompt patterns |
| `test_custom_splitters()` | Tests `extract_terms` with custom splitters |
| `test_custom_connectors()` | Tests `extract_terms` with custom connectors |
| `test_clean_term(input_term, expected)` | Parametrized unit test for `clean_term` |
| `test_deduplicate_terms_logic()` | Verifies highest weight is retained when deduplicating |
| `test_filter_terms_with_connectors()` | Verifies stopwords removed unless in connectors/splitters |
| `test_extract_weight_from_paren(text, expected)` | Parametrized unit test for `extract_weight_from_paren` |

---

## `infrastructure/external_services/mediapipe_models.py`

### Module-level functions

| Name | Description |
|---|---|
| `download_mediapipe_models()` | Downloads configured attribute models with URLs into the mediapipe models directory, skipping existing files |
| `_download_to(url, dest, key)` | Streams a URL to a temp file and atomically moves it to the destination, cleaning up on failure |

---

## `infrastructure/loading/maps_loader.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `AGE_CATEGORIES` | Fixed vocabulary for the age map |
| `GENDER_CATEGORIES` | Fixed vocabulary for the gender map |
| `RACE_CATEGORIES` | Fixed vocabulary for the race map |
| `ANALYSIS_CATEGORIES` | Fixed vocabulary for the analysis map |

### Class `MapsLoader`

| Name | Description |
|---|---|
| `__init__()` | Initializes the mapping dict with fixed category vocabularies and seeds missing fixed-category map files |
| `get_all_categories(name)` | Returns a copy of the registered categories for a map name or an empty list |
| `register_value(name, value)` | Idempotently adds a value and its sub-keys to a map, skipping empties and duplicates |
| `add_value(name, value)` | Appends a value to a map, saves the map file, and returns the new index and map length |
| `get_value(name, value)` | Returns the index of a value in a map (or -1) and the current map length |
| `_save_single_map(name)` | Writes a map's category list to its JSON file in the maps directory |
| `_load_single_map(name)` | Loads a map list from its JSON file, creating one containing unknown if absent |
| `load_maps()` | Loads all empty maps from disk and returns the full mapping |

---

## `infrastructure/loading/training_loader.py`

### Class `TrainingLoader`

| Name | Description |
|---|---|
| `__init__(use_cache)` | Stores the use_cache flag and initializes empty caches for vectors, scores, comparisons, and rules |
| `_reset_models()` | Clears all cached model, vector, score, comparison, and rule attributes |
| `remove_training_models()` | Deletes the models directory and resets all cached training models |
| `load_vectors()` | Loads vectors keyed by filename from cache, npz, or jsonl, caching as npz, and raises if the source is absent |
| `load_vectors_array()` | Returns vectors as a numpy array in filename order, caching the result |
| `_load_vectors_from_jsonl()` | Parses the vectors JSONL into a filename-keyed float32 dict |
| `_load_vectors_from_npz()` | Loads cached vectors from the npz file if present, else returns None |
| `_save_vectors_to_npz(keyed)` | Saves vectors and keys as a compressed npz cache in the models directory |
| `load_scores()` | Loads scores keyed by filename from cache, npz, or jsonl, caching as npz, and raises if the source is absent |
| `load_scores_array()` | Returns scores as a numpy array in filename order, caching the result |
| `_load_scores_from_jsonl()` | Parses the scores JSONL into a filename-keyed float dict |
| `_load_scores_from_npz()` | Loads cached scores from the npz file if present, else returns None |
| `_save_scores_to_npz(keyed)` | Saves scores and keys as a compressed npz cache in the models directory |
| `load_comparison_rows()` | Loads ordered comparison rows from cache, npz, or jsonl, caching as npz, and raises if the source is absent |
| `load_comparison_counts()` | Returns per-filename comparison counts derived from the loaded comparison rows |
| `_load_comparisons_from_npz()` | Loads cached comparison rows from the npz file if present, else returns None |
| `_save_comparisons_to_npz(rows)` | Saves comparison rows as a compressed npz cache in the models directory |
| `load_feature_rule()` | Loads the cached kept-indices feature rule from npz if present, else returns None |
| `save_feature_rule(kept_indices)` | Saves the kept-indices feature rule to a compressed npz and caches it |
| `load_comparison_rule(threshold)` | Returns the cached subset rule for a threshold, treating a threshold mismatch as a cache miss |
| `save_comparison_rule(threshold, rule)` | Saves the threshold-keyed subset rule to a compressed npz and caches it |
| `load_interaction_data()` | Loads cached interaction data X and indices from npz if present, else returns None |
| `save_interaction_data(x, top_k_indices_local)` | Saves interaction data to a compressed npz, caches it, and returns it |
| `_normalize(val)` | Converts 0-d numpy arrays to scalars and returns copies of larger arrays |
| `load_training_model_diagnostics()` | Loads all diagnostic arrays from the training model npz as a dict |
| `load_training_model()` | Loads the pickled model encoded as base64 in the training model npz, raising if the key is missing |
| `save_training_model(model, additional_data)` | Pickles and base64-encodes a model and saves it with diagnostics into a single npz file |

---

## `infrastructure/ml_models/batch_sizer.py`

### Class `HistoryEntry`

> Dataclass storing a batch size, delta memory, and timestamp for one profiling run

| Field | Description |
|---|---|
| `batch_size` | Candidate batch size profiled |
| `delta_memory` | Peak memory delta recorded for the batch |
| `timestamp` | Time the profiling run was recorded |

### Class `ProfileData`

> Dataclass storing model, device, memory, fit parameters, and per-resolution history entries

| Field | Description |
|---|---|
| `model_name` | Model key the profile belongs to |
| `device_name` | Device name the profile was measured on |
| `device_id` | CUDA device id |
| `total_memory` | Total device memory in bytes |
| `model_memory_bytes` | Memory occupied by the model in bytes |
| `fixed_overhead` | Fitted fixed memory overhead |
| `pixel_cost` | Fitted per-pixel memory cost |
| `r_squared` | Goodness of fit of the linear memory model |
| `history` | Per-resolution lists of profiling runs |

### Class `BatchSizer`

| Name | Description |
|---|---|
| `__init__(model_key)` | Stores the model key and clears the active profile and ready flag |
| `_ensure_session_profiled()` | Loads cached profiles and selects or creates the active profile for the model and CUDA device |
| `_resolution_key(width, height)` (staticmethod) | Returns a normalized WxH resolution key with the dimensions sorted |
| `get(width, height, rebuild, bound=None)` | Returns the best cached batch size for a resolution or profiles a new one, bounded by bound when given |
| `_profile_new_resolution(width, height, rebuild, bound=None)` | Binary-searches the largest safe batch size by running the model, then refits and saves the profile cache |
| `_evaluate_candidate()` | Runs the model on a candidate batch, records peak memory in history, and returns the size if under the safety threshold |
| `_fit_model()` | Fits a linear memory model from history, computing fixed overhead, pixel cost, and r-squared |
| `_save_cache()` | Writes the active profile and history to the vectors size JSON file |

---

## `infrastructure/ml_models/model_loader.py`

### Module-level functions

| Name | Description |
|---|---|
| `_missing_model_error(description)` | Returns a RuntimeError telling the user to download the named model |
| `_face_attributes_checkpoint_path(name)` | Returns the local safetensors checkpoint path for a HuggingFace model name |
| `verify_models_present()` | Checks all configured models exist locally and raises a RuntimeError listing missing ones |
| `download_configured_models()` | Loads every configured vision, embedding, and attribute model with download mode enabled |

### Class `MultiTaskClipVisionModel` (nn.Module)

| Name | Description |
|---|---|
| `__init__(num_labels)` | Builds a CLIP vision model with age, gender, and race linear heads sized from num_labels |
| `forward(pixel_values)` | Runs pixel values through the CLIP vision model and returns pooled logits for the three attribute heads |

### Class `ModelLoader`

| Name | Description |
|---|---|
| `__init__()` | Initializes embedding, vision, and HF model caches, the HF lock, and stores the prepare config |
| `_select_transform(name)` (staticmethod) | Returns the CLIP normalization for names containing clip, else the ImageNet normalization |
| `load_vision_model(model_key)` | Loads a timm vision model onto CUDA, caching the model, output dim, total memory, and transform |
| `get_model_info(model_key)` | Returns cached variable_input and input_size info for a model key, loading the model if needed |
| `load_embedding_model()` | Loads a SentenceTransformer embedding model onto CUDA, caching it with its output dim |
| `load_hf_vision_model(model_key)` | Returns the cached HuggingFace vision model or loads it once under a lock |
| `_load_hf_vision_model_impl(model_key)` | Loads the face_attributes or nsfw HuggingFace model and processor, downloading the checkpoint in download mode |

---

## `infrastructure/ml_models/training/model_trainer.py`

### Module-level functions

| Name | Description |
|---|---|
| `around(label, val)` | Returns a small sorted grid of candidate values around a hyperparameter, clamped and randomly mutated |

### Class `ModelTrainer`

| Name | Description |
|---|---|
| `__init__()` | Stores the training model, eval metrics, hyperparameters, verbosity, callbacks, and result metrics |
| `r2_metric(y_true, y_pred)` | Custom LightGBM evaluation callback returning the R2 score and a higher-is-better flag |
| `_pairwise_accuracy(y_true, y_pred)` (staticmethod) | Computes pairwise accuracy over flattened 2-row comparison groups, returning None if no pairs exist |
| `_build_score_calibration(X)` | Builds a fixed raw-to-score calibration for lambdarank models from loaded scores, else returns None |
| `create_training_model(config_dict)` | Creates the LightGBM ranker, classifier, or regressor from config and stores the matching eval metrics |
| `create_callbacks(progress_bar, status_bar, enable_plotting)` | Builds LightGBM callbacks for log evaluation, early stopping, and progress updates |
| `create_metrics(y_test, y_pred, training_time)` | Computes objective-aware metrics and evaluation curves and stores them in result_metrics |
| `train_model_pairs(config_dict, X, comparisons, index_list, enable_plotting)` | Trains a lambdarank model on pairwise comparison data with a train/valid split and returns the model and metrics |
| `train_model(config_dict, X, y, enable_plotting)` | Trains the configured LightGBM model, delegating lambdarank to pairwise training, and returns the model and metrics |

---

## `infrastructure/ml_models/training/pair_data.py`

### Module-level functions

| Name | Description |
|---|---|
| `load_comparison_records()` | Loads comparison dicts from the comparisons JSONL file |
| `build_pairwise_dataset(x, index_list, comparisons)` | Builds winner/loser row pairs with labels, group sizes, and weights from comparisons, returning them and the valid pair count |

---

## `infrastructure/persistence/cleanup_orphans.py`

> Cleanup orphaned image / JSON companion files inside the scored folder

### Module-level functions

| Name | Description |
|---|---|
| `_walk_all_files(root)` | Groups image and JSON files by stem across the whole root tree |
| `_scored_root_files(root)` | Groups image and JSON files by stem directly inside the root folder |
| `cleanup_orphans(root, dry_run, delete_enabled)` | Moves files lacking a companion to the root, pairs to scored_0.5, deletes singletons, and returns the resolved count |
| `main()` | Parses CLI arguments and runs the orphan cleanup |

### Module-level constants

| Symbol | Description |
|---|---|
| `IMAGE_EXTENSIONS` | Image file extensions treated as candidates |

---

## `infrastructure/persistence/comparisons_repository.py`

> Comparisons table operations

> **Scheduled deletion (REORGANIZATION_PLAN §0.1):** `get_recent_comparisons`, `get_comparison_count`, `delete_comparisons_for_image`, `delete_comparison_by_id`, and `delete_comparison` are dead — none are in the `ComparisonRepository` protocol and none have callers.

### Module-level functions

| Name | Description |
|---|---|
| `_canonicalize_pair(filename_a, filename_b)` | Returns the two filenames in sorted order |
| `_safe_parse_timestamp(timestamp)` | Parses a timestamp string safely, returns `(error_flag, datetime)` |
| `add_historical_comparison(filename_a, filename_b, winner, timestamp, weight, transitive_depth)` | Inserts a historical comparison row if no exact duplicate exists |
| `add_comparison(filename_a, filename_b, winner, weight, transitive_depth, timestamp)` | Records a new comparison result |
| `comparison_exists_for_pair(filename_a, filename_b)` | Checks whether any comparison exists for a given image pair |
| `clear_all_comparisons()` | Deletes all rows from the comparisons table |
| `get_recent_comparisons(filename, days, limit)` | Returns recent comparisons involving a specific file within a time window |
| `get_comparison_count(filename)` | Returns total number of comparisons involving a specific file |
| `get_total_comparisons()` | Returns total count of all comparison records |
| `get_skipped_comparison_count()` | Returns count of comparisons with `weight < 1.0` |
| `get_all_comparisons(weight)` | Returns all comparisons, optionally filtered by weight, ordered by timestamp |
| `get_images_with_only_wins()` | Returns filenames that have only won (never lost a comparison) |
| `get_images_with_only_losses()` | Returns filenames that have only lost (never won a comparison) |
| `delete_comparisons_for_image(filename)` | Deletes all comparisons involving a specific image |
| `delete_comparison_by_id(comp_id)` | Deletes a single comparison by its primary key ID |
| `delete_comparison(filename_a, filename_b, winner)` | Deletes a specific comparison by its three key fields |
| `clean_comparisons()` | Cleans comparison history: removes missing-node refs, self-links, duplicates, contradictions |

---

## `infrastructure/persistence/database.py`

> Database schema definitions and connection management

> **Scheduled deletion (REORGANIZATION_PLAN §0.1):** `get_meta_value` is dead — no callers.

### Module-level functions

| Name | Description |
|---|---|
| `get_db_connection()` | Creates and returns a SQLite connection with row factory and WAL pragmas |
| `_ensure_meta_table(conn)` | Creates the `meta` table if it does not exist |
| `_ensure_images_table(conn)` | Creates/migrates the `images` table with indexes, adding missing columns |
| `_ensure_comparisons_table(conn)` | Creates the `comparisons` table with indexes |
| `init_database()` | Creates all tables, sets initial meta values (`db_version`, `ranking_generation`) |
| `_set_meta_value(key, value)` | Upserts a key-value pair into the `meta` table |
| `get_meta_value(key)` | Retrieves a value from the `meta` table by key |
| `vacuum_database()` | Runs `VACUUM` on the database |

### Module-level constants

| Symbol | Description |
|---|---|
| `MU0` | Initial TrueSkill rating mean |
| `SIGMA0` | Initial TrueSkill rating uncertainty |

---

## `infrastructure/persistence/deduplicate_scored.py`

> Deduplicate scored images by comparing companion image MD5 across tier folders

### Module-level functions

| Name | Description |
|---|---|
| `_md5(path)` | Returns the hex MD5 digest of a file's bytes |
| `_merge_comparison_histories(keeper, discard, filename)` | Merges comparison histories from discarded copies into the keeper entry, deduplicating by comparison id |
| `deduplicate_scored(root, dry_run, limit)` | Deduplicates scored images by MD5 across tier folders, merging histories and renaming conflicts, returning the resolved count |
| `main()` | Parses CLI arguments and runs the scored folder deduplication |

---

## `infrastructure/persistence/folder_organizer.py`

> Folder organizer - maintain score folder structure

### Module-level functions

| Name | Description |
|---|---|
| `ensure_tier_structure()` | Creates the scored_0.0 through scored_1.0 folders under the ranked root, returning success |

---

## `infrastructure/persistence/images_repository.py`

> Images table operations

> **Scheduled deletion (REORGANIZATION_PLAN §0.1):** `update_image_score`, `get_scored_images`, `get_images_by_tier`, and `delete_image` are dead — none are in the `ImageRepository` protocol and none have callers.

### Module-level functions

| Name | Description |
|---|---|
| `get_all_images()` | Returns all image rows from the images table as dicts |
| `get_image(filename)` | Returns the image row for a filename or None |
| `add_image(filename, score, comparison_count, prompt_tags, rating_mu, rating_sigma)` | Inserts a new image row with INSERT OR IGNORE and commits |
| `update_image_rating_state(filename, score, rating_mu, rating_sigma, comparison_count, touch_timestamp, last_compared_at)` | Updates score, rating, and comparison count, optionally touching or setting last_compared_at, returning success |
| `update_image_tags(filename, prompt_tags)` | Updates the prompt_tags column for a filename, returning success |
| `update_image_score(filename, score)` | Updates the score for a filename and stamps last_compared_at, returning success |
| `get_image_count()` | Returns the total number of image rows |
| `get_scored_images(limit, offset)` | Returns scored images ordered by score descending with limit and offset plus the total scored count |
| `get_images_by_tier(tier)` | Returns images whose score falls within the given tenth-based tier range |
| `delete_image(filename)` | Deletes the image row for a filename and returns whether a row was removed |
| `clear_all_images()` | Deletes all image rows and returns the number deleted |
| `reset_all_image_ratings(score)` | Resets score, ratings, comparison count, and last_compared_at for all images, returning success |

---

## `infrastructure/persistence/path_handler.py`

> Path handler - compute tier structure from scores and sync companion JSON

> **Scheduled deletion (REORGANIZATION_PLAN §0.1):** `append_comparison_history_to_json` is dead — no callers (and it has 3 unused args per §6b).

### Module-level functions

| Name | Description |
|---|---|
| `prewarm_folder_cache(ranked_root)` | Populates the tier folder listdir cache for all existing scored_X.X directories |
| `clear_folder_cache()` | Clears the folder listdir cache |
| `get_ranked_root()` | Returns the absolute processed image root path, creating it if missing |
| `compute_path_from_filename(filename, score)` | Computes the scored folder destination for a filename from its clamped score and subfolder threshold |
| `find_image_path(filename)` | Walks the ranked root and returns the path containing the given filename or None |
| `_build_history_for_filename(filename, all_comparisons, filename_to_comparisons, filename_to_image_data)` | Builds a sorted comparison history list for a filename with opponent scores and weights |
| `_move_image_and_json(current_image, current_json, score)` | Moves an image and its companion JSON into the folder matching the new score |
| `sync_image_metadata_to_json(filename, score, rating_mu, rating_sigma, comparison_count, all_comparisons, filename_to_path, filename_to_comparisons, filename_to_image_data, filename_to_entry)` | Rewrites a JSON companion file with DB-backed score, ratings, count, and history, then moves the pair, returning success |
| `append_comparison_history_to_json(filename, comparison_data, new_score, new_rating_mu, new_rating_sigma)` | Compatibility wrapper that performs a full DB-backed JSON sync from stored image data |

---

## `scorer.py`

| Name | Description |
|---|---|
| *(module-level script)* | **Main CLI entry point** — imports `main` from `adapters.cli.main` and exits with its return code; run as `python scorer.py <command>` from the module root (kept — see REORGANIZATION_PLAN §2.3 item 6) |

---

## Documented paths not yet on disk (from README / REORGANIZATION_PLAN)

The README and REORGANIZATION_PLAN describe the following paths that do not exist on disk yet. They are tracked here so the index and the docs stay in sync.

| Path | Documented intent |
|---|---|
| `domain/loading/` | README `domain/` section: loader **port interfaces** (aesthetic, MediaPipe, maps). REORGANIZATION_PLAN Phase 2a creates `domain/loading/ports.py` with protocols `ModelLoader`, `BatchSizer`, `MapsProvider`, `TrainingLoader`. Loader implementations live in `infrastructure/loading/` and `infrastructure/ml_models/` |
| `tests/test_architecture.py` | README “Dependency Violation Test”; REORGANIZATION_PLAN Phase 5. AST-based layer-import scan; not created while test authoring is on hold |
| `adapters/comfyui/services.py` | REORGANIZATION_PLAN Phase 2e: wiring module that builds `ScoringService` with infrastructure singletons; the node (`adapters/comfyui/nodes/aesthetic_score/node.py`) currently imports `ScoringService` and `verify_models_present` directly |
| `infrastructure/persistence/` `SQLiteImagesRepository` / `SQLiteComparisonsRepository` | REORGANIZATION_PLAN Phase 2b: thin classes implementing `ImageRepository` / `ComparisonRepository` (defined in `domain/database/ports/repository_ports.py`) that delegate to the existing free functions in `images_repository.py` / `comparisons_repository.py` |
| `application/data_transform/__init__.py`, `application/hyperparameters/__init__.py` | Exist as **directories** (namespace packages), not files; REORGANIZATION_PLAN Phase 1 defect (`§2.3` item 1) replaces them with real `__init__.py` files |
| Empty shells (only `__init__.py`): `application/dto/`, `application/ports/`, `adapters/server/middleware/`, `adapters/server/tests/`, `domain/database/tests/` | REORGANIZATION_PLAN `§2.3` item 8; documented layout (README `application/dto` + `ports`, `adapters/server/middleware` + tests) awaiting content |
| `pyrightconfig.json` | Static type checker config referenced by README/REORGANIZATION_PLAN — **missing on disk** (deleted in commit `7397304`); must be recreated (strict mode, exclude `comfyui_image_scorer_old/`) before the `pyright` gate can run (plan `§2.3` item 9) |
| `comfyui_image_scorer_old/` | Legacy reference copy of the pre-reorganization codebase; REORGANIZATION_PLAN states it is removed manually by the user and is **excluded** from this index |
