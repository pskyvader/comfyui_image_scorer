# Function Index — comfyui_image_scorer

Generated from the live tree (paths relative to `comfyui_image_scorer`). Files are ordered by layer following the layout in `README.md`; see the last section for paths `README.md`/`REORGANIZATION_PLAN.md` describe that are not yet on disk. `comfyui_image_scorer_old/` is excluded.

## `__init__.py`

| Name | Description |
|---|---|
| `__all__` | Exports ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS'] |
| `NODE_CLASS_MAPPINGS` | Re-exported through `__all__` |
| `NODE_DISPLAY_NAME_MAPPINGS` | Re-exported through `__all__` |

### Module-level functions

| Name | Description |
|---|---|
| `__getattr__(name)` | — |


## `scorer.py`


## `core\__init__.py`

> Core shared infrastructure — configuration, filesystem paths, IO serialization, logging/observability, and generic concurrency utilities.


## `core\configuration\__init__.py`

> Configuration management — hierarchical JSON settings with auto-saving sub-configs, lazy loading, caching, and the AutoSaveDict mutable-mapping wrapper.


## `core\configuration\settings.py`

### Module-level functions

| Name | Description |
|---|---|
| `_get_config_file(path)` | — |
| `_load_raw_config(path)` | — |
| `_save_raw_config(data, path)` | — |
| `ensure_dir(path)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `PathLike` | `str | Path` |
| `ConfigDict` | `dict[str, Any]` |
| `PROJECT_ROOT` | `Path(__file__).resolve().parents[2]` |
| `CONFIG_FILE` | `PROJECT_ROOT.joinpath('config', 'config.json')` |
| `SUB_CONFIG_MAPPING` | `{'prepare': 'prepare_config', 'training': 'training_config', 'vector': 'vector_config', 'ranking': 'ranking_config'}` |
| `_sentinel` | `object()` |
| `config` | Global singleton |

### Class `AutoSaveDict` (MutableMapping)

| Name | Description |
|---|---|
| `__init__(data, save_callback)` | — |
| `get(key, default=_sentinel)` | — |
| `__getitem__(key)` | — |
| `__setitem__(key, value)` | — |
| `__delitem__(key)` | — |
| `__iter__()` | — |
| `__len__()` | — |
| `copy()` | — |
| `__repr__()` | — |

### Class `Config` (MutableMapping)

> Configuration Manager.

| Name | Description |
|---|---|
| `__init__(config_file=CONFIG_FILE)` | — |
| `get(key, default=_sentinel)` | — |
| `_get_root()` | — |
| `_save_root()` | — |
| `_get_sub(section)` | — |
| `_save_sub(section)` | — |
| `__getitem__(key)` | — |
| `__setitem__(key, value)` | — |
| `__delitem__(key)` | — |
| `__iter__()` | — |
| `__len__()` | — |
| `clear()` | Clear cache to force reload from disk. |


## `core\filesystem\__init__.py`

> Filesystem path resolution — module-level Path constants for output, cache, maps, vectors, models, and mediapipe directories, relative to project root.


## `core\filesystem\paths.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `root` | `Path(__file__).parents[2]` |
| `output_dir` | config_dir: str = os.path.join(root, "config") |
| `maps_dir` | config_dir: str = os.path.join(root, "config") |
| `cache_file` | `os.path.join(output_dir, 'cache.db')` |
| `image_root` | `config['image_root']` |
| `image_root_processed` | `os.path.join(image_root, 'scored')` |
| `vectors_size_file` | `os.path.join(output_dir, 'image_vector_size.json')` |
| `vectors_dir` | `os.path.join(output_dir, 'vectors')` |
| `split_dir` | `os.path.join(vectors_dir, 'split')` |
| `vectors_file` | `os.path.join(vectors_dir, 'vectors.jsonl')` |
| `scores_file` | `os.path.join(vectors_dir, 'scores.jsonl')` |
| `comparisons_file` | `os.path.join(vectors_dir, 'comparisons.jsonl')` |
| `index_file` | `os.path.join(vectors_dir, 'index.jsonl')` |
| `text_data_file` | `os.path.join(vectors_dir, 'text_data.jsonl')` |
| `models_dir` | `os.path.join(output_dir, 'models')` |
| `mediapipe_models_dir` | `os.path.join(output_dir, 'downloaded_models')` |
| `training_plots_dir` | `os.path.join(output_dir, 'training', 'plots')` |
| `training_model` | `os.path.join(models_dir, 'model.npz')` |
| `vectors_data` | `os.path.join(models_dir, 'vectors.npz')` |
| `scores_data` | `os.path.join(models_dir, 'scores.npz')` |
| `comparisons_data` | `os.path.join(models_dir, 'comparisons.npz')` |
| `feature_rule` | `os.path.join(models_dir, 'feature_rule.npz')` |
| `comparison_rule` | `os.path.join(models_dir, 'comparison_rule.npz')` |
| `interaction_data` | `os.path.join(models_dir, 'interaction_data.npz')` |


## `core\io\__init__.py`

> IO and serialization — JSONL streaming (load/write), atomic JSON writes via temp file + replace, recursive JSON parsing, filesystem discovery of image/metadata pairs, and multi-file batch collection (collect_valid_files).


## `core\io\serialization.py`

### Module-level functions

| Name | Description |
|---|---|
| `load_single_jsonl(filename, skip_invalid=True)` | — |
| `write_single_jsonl(filename, data, mode)` | — |
| `discover_files(root)` | — |
| `collect_single_file(file)` | — |
| `collect_valid_files(files, max_workers, scored_only)` | — |
| `_recursive_parse_json(obj, path)` | — |
| `load_json(path, expect)` | — |
| `atomic_write_json(path, data, *, indent)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |


## `core\observability\__init__.py`

> Observability/logging — SharedLogger and ModuleLogger with configurable level/filter hooks, synchronous log capture for command endpoints, and CustomFormatter for trimmed log output.


## `core\observability\logger.py`

> Shared backend logging utilities.

### Module-level functions

| Name | Description |
|---|---|
| `_custom_find_caller(_self, stack_info=False, _stacklevel=1)` | — |
| `capture_log_output()` | Collect log output (package log records + stdout/stderr writes) during |
| `get_logger(module_name=None)` | — |
| `get_logger(module_name)` | — |
| `get_logger(module_name=None)` | — |
| `configure_package_logging(level=logging.INFO, fmt=None, *, datefmt='%H:%M:%S', trim_level_len=3, trim_module_len=15, trim_func_len=15, trim_msg_len=None)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `LogLevelName` | `Literal['debug', 'info', 'warning', 'error', 'critical']` |

### Class `_CaptureHandler` (logging.Handler)

> Collects formatted package log records into a line list.

| Name | Description |
|---|---|
| `__init__(lines, level)` | — |
| `emit(record)` | — |

### Class `_DynamicModuleFilter` (logging.Filter)

| Name | Description |
|---|---|
| `filter(record)` | — |

### Class `ModuleLogger`

| Name | Description |
|---|---|
| `__init__(module_name)` | — |
| `_underlying()` (property) | — |
| `level()` (property) | — |
| `level(value)` | — |
| `setLevel(level)` | — |
| `addHandler(hdlr)` | — |
| `removeHandler(hdlr)` | — |
| `log(level_name, message, *args, start_timer=None)` | — |
| `debug(message, *args, start_timer=None)` | — |
| `info(message, *args, start_timer=None)` | — |
| `warning(message, *args, start_timer=None)` | — |
| `error(message, *args, start_timer=None)` | — |
| `exception(message, *args, start_timer=None)` | — |
| `critical(message, *args, start_timer=None)` | — |

### Class `SharedLogger`

> Centralized backend logger.

| Name | Description |
|---|---|
| `install_root_filter()` (classmethod) | — |
| `set_name_filters(exact_names, prefixes)` (classmethod) | — |
| `clear_name_filters()` (classmethod) | — |
| `should_emit(module_name)` (classmethod) | — |
| `get_logger(module_name)` (classmethod) | — |
| `format_message(message, start_timer)` (classmethod) | — |
| `log(module_name, level_name, message, start_timer)` (classmethod) | — |
| `_normalize_level(level_name)` (staticmethod) | — |

### Class `CustomFormatter` (logging.Formatter)

> Custom formatter to trim level names, module names, function names, and messages.

| Name | Description |
|---|---|
| `__init__(fmt=None, datefmt=None, trim_level_len=3, trim_module_len=15, trim_func_len=15, trim_msg_len=None)` | — |
| `format(record)` | — |


## `core\utilities\__init__.py`

> Generic concurrency utilities — sequential batch executor (parallel_batch) and ThreadPoolExecutor with tqdm progress bar (parallel_for).


## `core\utilities\analysis.py`

> Core utility analysis helpers (stateless functions).

### Module-level functions

| Name | Description |
|---|---|
| `distribute(values, buckets)` | Distribute values into named buckets by threshold. |


## `core\utilities\concurrency.py`

### Module-level functions

| Name | Description |
|---|---|
| `parallel_batch(fn, items)` | — |
| `parallel_for(fn, items, *, max_workers=1, batch_size=0, desc='Processing', unit='items', on_progress=None)` | Execute fn(*item) for each item across a thread pool. |

### Module-level constants

| Symbol | Description |
|---|---|
| `R` | `TypeVar('R')` |
| `logger` | `get_logger(__name__)` |


## `core\utilities\helpers.py`

### Module-level functions

| Name | Description |
|---|---|
| `remove_directory(directory_path)` | — |
| `delete_full_vectors()` | Delete the full vector files and all split categories except image/. |
| `remove_models()` | — |
| `remove_derived_caches(*paths)` | Delete only the named derived cache files. Each file is removed |
| `export_image_batch(pil_images)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |


## `domain\__init__.py`

> Domain layer — graph models (chain_manager, node_proxy, chain_proxy, component_proxy), prompt/term extraction, and database port interfaces.


## `domain\analysis\__init__.py`


## `domain\analysis\attribute_analysis.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `AGE_LABELS` | Category order MUST match maps_loader.AGE/GENDER/RACE_CATEGORIES (model output index order). |
| `GENDER_LABELS` | `['Female', 'Male']` |
| `RACE_LABELS` | `['Black', 'East Asian', 'Indian', 'Latino_Hispanic', 'Middle Eastern', 'Southeast Asian', 'White']` |

### Class `FaceAttributeAnalyzer`

> Predicts perceived age, gender, and race from face images.

| Name | Description |
|---|---|
| `__init__(model_loader)` | — |
| `_ensure_loaded()` | — |
| `predict(img)` | — |
| `predict_batch(imgs)` | — |

| Class constant | Description |
|---|---|
| `MODEL_KEY` | `'face_attributes'` |

### Class `NSFWAnalyzer`

> Predicts NSFW probability for an image using a ViT classifier.

| Name | Description |
|---|---|
| `__init__(model_loader)` | — |
| `_ensure_loaded()` | — |
| `predict(img)` | — |
| `predict_batch(imgs)` | — |

| Class constant | Description |
|---|---|
| `MODEL_KEY` | `'nsfw'` |


## `domain\analysis\image_analysis.py`

### Module-level functions

| Name | Description |
|---|---|
| `process_single_batch(prepare_func, analyze_func, save_func, paths, data)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `ImageEntry` | Type Alias for the shared data structure |
| `REQUIRED_ANALYSIS_FIELDS` | `{'original_width', 'original_height', 'final_width', 'final_height', 'final_aspect_ratio', 'original_aspect_ratio', 'analysis', 'bbox', *POSE_LANDMARK_NAMES, 'age', 'gender', 'race', 'nsfw_score'}` |
| `METRIC_KEYS` | `['contrast', 'sharpness', 'noise_score', 'colorfulness', 'artifact_score', 'edge_density', 'texture_lbp']` |

### Class `ImageAnalysis` (ImageVector)

| Name | Description |
|---|---|
| `__init__(raw_data, model_loader, batch_sizer_factory)` | — |
| `_entry_has_required_fields(entry)` (staticmethod) | — |
| `_entry_json_path(entry)` (staticmethod) | — |
| `_save_entry_sidecar(entry)` | — |
| `_image_size(img, entry, data)` | — |
| `_contrast(img, entry)` | — |
| `_sharpness(img, entry)` | — |
| `_noise_score(img, entry)` | — |
| `_colorfulness(img, entry)` | — |
| `_artifact_score(img, entry)` | — |
| `_edge_density(img, entry)` | — |
| `_texture_lbp(img, entry)` | — |
| `_mediapipe_analysis(img, entry)` | — |
| `_assemble_analysis_map(entry)` | — |
| `_nsfw_analysis(img, entry)` | — |
| `_run_face_pass(entries)` | — |
| `_run_nsfw_pass(entries)` | — |
| `analyze_image_batch(image_batch, data_batch)` | — |
| `_normalize_lora(entry)` (staticmethod) | Fold the legacy scalar ``lora_weight`` into the ``lora`` map. |
| `analyze_images_from_paths(batch_size, max_workers)` | — |


## `domain\analysis\mediapipe_analysis.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `POSE_LANDMARK_NAMES` | MediaPipe Pose landmark names, in model output order (0..32). |

### Class `MediaPipeAnalyzer`

> Detects faces and body pose using MediaPipe.

| Name | Description |
|---|---|
| `__init__()` | — |
| `_image_to_rgb(img)` | — |
| `_get_face_detector()` | — |
| `_get_pose_landmarker()` | — |
| `analyze(img)` | — |


## `domain\analysis\trueskill.py`

### Module-level functions

| Name | Description |
|---|---|
| `normal_cumulative_distribution(x)` | — |
| `_clamp_uncertainty(uncertainty)` | — |
| `expected_win_probability(first_rating, second_rating)` | — |
| `public_score_from_rating(rating)` | — |
| `normal_probability_density(x)` | — |
| `_add_dynamics_noise(uncertainty)` | — |
| `update_ratings(winner, loser)` | — |
| `replay_ratings(rows)` | — |
| `rating_from_row(row)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `INITIAL_MEAN` | `25.0` |
| `INITIAL_UNCERTAINTY` | `INITIAL_MEAN / 3.0` |
| `PERFORMANCE_VARIATION` | `INITIAL_MEAN / 6.0` |
| `DYNAMICS_NOISE` | `INITIAL_MEAN / 300.0` |
| `EPSILON` | `1e-09` |
| `SCORE_STEEPNESS` | `float(config['ranking']['score_steepness'])` |

### Class `Rating`


## `domain\comparison\__init__.py`


## `domain\comparison\algorithm\__init__.py`

> Algorithm package for comparison/ranking.


## `domain\comparison\algorithm\graph_helpers.py`

> Reusable graph-query helpers for the ranking algorithm.

### Module-level functions

| Name | Description |
|---|---|
| `pair_key(filename_a, filename_b)` | — |
| `stable_seed_pool(images)` | — |
| `is_collapsable_pair(filename_a, filename_b, cg)` | Check if a pair is collapsible (both top or both bottom in same component, no common chains). |
| `filter_excluded_images(images, exclude_set)` | Remove images whose filename is in exclude_set. |

### Class `CrystalGraph` (Protocol)

| Name | Description |
|---|---|
| `get_node(node_id=None)` | — |
| `get_component(node_id=None, component_id=None, chain_id=None)` | — |
| `are_in_same_path(img1, img2)` | — |


## `domain\comparison\algorithm\merge_sort_ranker.py`

> Public orchestration layer for step01 pair selection and comparison recording.

### Module-level functions

| Name | Description |
|---|---|
| `select_pair_for_comparison(exclude_set, crystal_graph)` | Select the next pair of images to compare. |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |

### Class `CrystalGraph` (Protocol)

| Name | Description |
|---|---|
| `is_cache_stale()` | — |
| `rebuild_from_database(images=None, comparisons=None)` | — |
| `get_node(node_id=None)` | — |
| `get_all_chains(min_length=0, sort_order='desc')` | — |
| `get_all_nodes(only_top=False, only_bottom=False)` | — |
| `get_graph_stats()` | — |
| `are_in_same_path(img1, img2)` | — |
| `get_main_chain_member_count(chain_id)` | — |


## `domain\comparison\algorithm\pair_active.py`

> Active pair selection for the TrueSkill-based step01 flow.

### Module-level functions

| Name | Description |
|---|---|
| `phase_seed_coverage(seed_candidates, existing_pair_set)` | — |
| `phase_anchor_insert(candidate_images, seed_pool, existing_pair_set, cg)` | — |
| `_collect_chain_extremes(chains, candidate_names, check_list, use_bottom, cg)` | Return up to 10 qualifying chain extremes, least-compared first. |
| `_closest_score_pair(pair_list)` | — |
| `phase_collapsible_pairs(candidate_images, cg)` | Anchor on the least-compared node and return its most score-similar same-type partner. |
| `_single_nodes(cg, candidate_names, insertion_target, single_win)` | — |
| `phase_single_win_loss(candidate_images, cg)` | — |
| `phase_chain_merge(candidate_images, cg)` | — |
| `phase_uncertainty_refine(candidate_images, pair_set, cg)` | — |
| `phase_fallback(candidate_images, pair_set)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `NodeTuple` | `tuple[NodeProxy, bool]` |
| `_last_chains_index` | `[]` |

### Class `CrystalGraph` (Protocol)

| Name | Description |
|---|---|
| `get_node(node_id=None)` | — |
| `get_all_nodes(only_top=False, only_bottom=False)` | — |
| `get_component(node_id=None, component_id=None, chain_id=None)` | — |
| `get_all_chains(min_length=0, sort_order='desc')` | — |
| `get_graph_stats()` | — |
| `are_in_same_path(img1, img2)` | — |


## `domain\comparison\algorithm\phase_order.py`

> Phase ordering configuration.

### Module-level functions

| Name | Description |
|---|---|
| `reset_skip()` | — |
| `get_phases()` | Return a JSON-serializable version of PHASES (callables stripped). |
| `select_pair(all_images, candidate_images, cg)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `SharedLogger.get_logger(__name__)` |
| `PHASES` | function).  Remaining keys are metadata consumed by the frontend. |
| `_skip_before` | `0` |


## `domain\comparison\algorithm\view.py`

> Read-only serialization of graph objects into comparison-frontend payloads.

### Module-level functions

| Name | Description |
|---|---|
| `_describe_one(node, cg)` | Build the per-image payload from a NodeProxy. |
| `describe_image(node, cg)` | Return all per-image info for a single node, regardless of phase. |
| `describe_pair(node_a, node_b, phase_index, cg)` | Return phase-specific pair context built from the two nodes and config. |


## `domain\comparison\comparison_recorder.py`

> Comparison recording and rating updates.

### Module-level functions

| Name | Description |
|---|---|
| `update_scores_after_comparison(winner_data, loser_data)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |

### Class `GraphService` (Protocol)

| Name | Description |
|---|---|
| `apply_comparison(winner, loser)` | — |

### Class `ComparisonRecorder`

| Name | Description |
|---|---|
| `__init__(path_syncer, graph_service)` | — |
| `_persist_image_state(filename, data)` | — |
| `record_comparison(filename_a, filename_b, winner, impact_factor, transitive_depth)` | Record one direct comparison and update both image ratings. |


## `domain\comparison\constants.py`

> Pair-type labels and tunable constants for the ranking algorithm.

### Module-level constants

| Symbol | Description |
|---|---|
| `IMAGES_CACHE_TTL` | `10` |
| `MAX_PAIR_CANDIDATES` | `100` |
| `MIN_CHAIN_THRESHOLD` | `20` |


## `domain\data_transformation\__init__.py`


## `domain\data_transformation\data_transformer.py`

### Module-level functions

| Name | Description |
|---|---|
| `get_feature_mapping_from_config()` | Creates a mapping from feature indices to vector names and positions. |
| `_label_position_slot(pos_in_unit)` | — |
| `_label_keypoint_slot(vec_name, pos_in_unit)` | — |
| `_label_person_map_slot(vec_name, pos_in_unit)` | — |
| `_load_map_slots(vec_name)` | Load the saved map JSON for a map-type vector, returning slot labels by index. |
| `_print_vector_summary(vec_name, vec_type, kept_in_vec, total_in_vec, slot_size, per_unit_size, start_idx=0)` | Print one vector line (or expanded lines for known multi-slot / map vectors). |
| `list_filtered_features(transformer)` | Loads the cached filtered features and prints a compact summary of which |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |

### Class `DataTransformer`

| Name | Description |
|---|---|
| `__init__(training_loader, model_trainer)` | — |
| `get_raw_data()` | — |
| `filter_low_comparisons(threshold=0)` | Return the kept subset as filename -> (score, count). |
| `filter_unused_features(vectors_keyed, scores_keyed, steps)` | Trains a fast LightGBM model on the keyed vectors/scores to identify and |
| `calculate_interaction_batch(X_batch, y_batch, n_features_in, accumulators)` | — |
| `compute_correlations(k, accumulators, n_samples, dtype)` | — |
| `build_interaction_batch(X_batch, top_k_indices_local, n_features_in)` | — |
| `add_interaction_features(x, y, target_k=500)` | Generates and selects top K interaction features (x*y) using batched processing |
| `apply_feature_filter(vecs)` | Applies the feature filter (kept_indices) from feature_rule.npz to the input vector. |
| `apply_interaction_features(vecs)` | Applies the interaction features (from interaction_data_cache.npz) to the input vector. |

| Class constant | Description |
|---|---|
| `poly` | `PolynomialFeatures(degree=2, include_bias=False, interaction_only=True)` |


## `domain\database\__init__.py`

> Database domain — port interfaces (ports/repository_ports.py: ImageRepository, ComparisonRepository, PathResolver protocols).


## `domain\database\ports\__init__.py`

> Domain database ports.

| Name | Description |
|---|---|
| `__all__` | Exports ['ImageRepository', 'ComparisonRepository', 'PathResolver'] |
| `ImageRepository` | Re-exported through `__all__` |
| `ComparisonRepository` | Re-exported through `__all__` |
| `PathResolver` | Re-exported through `__all__` |


## `domain\database\ports\repository_ports.py`

> Repository interface ports for domain isolation.

### Class `ImageRepository` (Protocol)

| Name | Description |
|---|---|
| `get_image(filename)` | — |
| `get_all_images()` | — |
| `get_image_count()` | — |
| `add_image(filename, score, comparison_count, prompt_tags, rating_mu, rating_sigma)` | — |
| `update_image_rating_state(filename, score, rating_mu, rating_sigma, comparison_count, touch_timestamp=True)` | — |
| `update_image_tags(filename, prompt_tags)` | — |
| `clear_all_images()` | — |
| `reset_all_image_ratings(score)` | — |

### Class `ComparisonRepository` (Protocol)

| Name | Description |
|---|---|
| `add_comparison(filename_a, filename_b, winner, weight=1.0, transitive_depth=0, timestamp=None)` | — |
| `add_historical_comparison(filename_a, filename_b, winner, timestamp, weight=1.0, transitive_depth=0)` | — |
| `comparison_exists_for_pair(filename_a, filename_b)` | — |
| `get_all_comparisons(weight=None)` | — |
| `get_total_comparisons()` | — |
| `get_skipped_comparison_count()` | — |
| `clean_comparisons()` | — |
| `get_images_with_only_wins()` | — |
| `get_images_with_only_losses()` | — |
| `clear_all_comparisons()` | — |

### Class `PathResolver` (Protocol)

| Name | Description |
|---|---|
| `sync_image_metadata_to_json(filename, score, rating_mu, rating_sigma, comparison_count, all_comparisons=None)` | — |


## `domain\graph\__init__.py`

> Graph/comparison-chains domain — ChainManager (graph construction from comparisons, topological chain building via DP on SCC-condensed DAG, top/bottom detection, component merging), proxy models (NodeProxy, ChainProxy, ComponentProxy).


## `domain\graph\chain_manager.py`

### Module-level functions

| Name | Description |
|---|---|
| `parse_comparison(comp)` | — |
| `add_directed_edge(better_than, worse_than, winner, loser)` | — |
| `add_undirected_edge(adjacency, filenames, filename_a, filename_b)` | — |
| `process_one_comparison(comp, better_than, worse_than, adjacency, filenames)` | — |
| `has_no_predecessors(node, better_than)` | — |
| `has_no_successors(node, worse_than)` | — |
| `find_top_nodes(all_filenames, better_than)` | — |
| `find_bottom_nodes(all_filenames, worse_than)` | — |
| `bfs_one_component(start, adjacency, visited)` | — |
| `index_component(members, comp_id, node_component, component_members)` | — |
| `build_components(all_filenames, adjacency)` | — |
| `same_component(u, v, node_component)` | — |
| `find_common_chain_id(node_chains, other_chains)` | — |
| `tarjan_scc(nodes, successors)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |

### Class `ChainManager`

| Name | Description |
|---|---|
| `__init__()` | — |
| `get_all_filenames()` | — |
| `get_top_nodes()` | — |
| `get_bottom_nodes()` | — |
| `get_better_than(node_id)` | — |
| `get_worse_than(node_id)` | — |
| `is_top(node_id)` | — |
| `is_bottom(node_id)` | — |
| `get_component_id(node_id)` | — |
| `get_component_members(comp_id)` | — |
| `get_component_count()` | — |
| `get_built_at()` | — |
| `set_built_at(dt)` | — |
| `get_db_comparison_count()` | — |
| `set_db_comparison_count(count)` | — |
| `build(comparisons, all_filenames=None)` | — |
| `_reset_adjacency()` | — |
| `_build_from_comparisons(comparisons)` | — |
| `apply_comparison(winner, loser)` | — |
| `_remove_from_bottom_if_not_anymore(winner)` | — |
| `_remove_from_top_if_not_anymore(loser)` | — |
| `_add_to_bottom_if_needed(loser)` | — |
| `_add_to_top_if_needed(winner)` | — |
| `_update_top_bottom_for_edge(winner, loser)` | — |
| `_component_of(node)` | — |
| `_both_have_components_and_different(cw, cl)` | — |
| `_neither_has_component(cw, cl)` | — |
| `_winner_lacks_component(cw, cl)` | — |
| `_loser_lacks_component(cw, cl)` | — |
| `_create_new_component(winner, loser)` | — |
| `_add_winner_to_loser_component(winner, cl)` | — |
| `_add_loser_to_winner_component(loser, cw)` | — |
| `_merge_node_components(winner, loser)` | — |
| `_ensure_larger_component_kept(keep_id, remove_id)` | — |
| `_reassign_nodes(remove_id, keep_id)` | — |
| `_absorb_removed_component(keep_id, remove_id)` | — |
| `_merge_components(keep_id, remove_id)` | — |
| `_identify_top_bottom()` | — |
| `_build_components()` | — |
| `_dedup_path(path)` (staticmethod) | — |
| `_build_chains()` | — |
| `get_chains()` | — |
| `get_node_chains(node_id)` | — |
| `get_node_main_chain(node_id)` | — |
| `get_min_chain_count()` | — |
| `_quick_reject(start, end)` | — |
| `_bfs_search(start, end, max_depth)` | — |
| `_can_reach(start, end)` | — |
| `_check_same_chain(u, v)` | — |


## `domain\graph\chain_proxy.py`

### Class `ChainProxy`

> Represents one directed path (chain). Created from min chain cover results.

| Name | Description |
|---|---|
| `__init__(chain, chain_id, node_list)` | — |
| `id()` (property) | — |
| `nodes()` (property) | — |
| `length()` (property) | — |
| `is_main()` (property) | — |
| `first()` (property) | — |
| `last()` (property) | — |
| `get_nodes(only_top=False, only_bottom=False)` | — |
| `node_position(node_id)` | — |
| `get_component()` | — |
| `__repr__()` | — |


## `domain\graph\component_proxy.py`

### Class `ComponentProxy`

> Represents one connected component.

| Name | Description |
|---|---|
| `__init__(chain, comp_id)` | — |
| `id()` (property) | — |
| `nodes()` (property) | — |
| `size()` (property) | — |
| `get_chains()` | — |
| `__repr__()` | — |


## `domain\graph\node_proxy.py`

### Class `NodeProxy`

> Represents one image/node in the graph. Created on demand, zero overhead.

| Name | Description |
|---|---|
| `__init__(chain, node_id, image_data=None)` | — |
| `id()` (property) | — |
| `filename()` (property) | — |
| `score()` (property) | — |
| `mu_skill()` (property) | — |
| `sigma_uncertainty()` (property) | — |
| `comparison_count()` (property) | — |
| `chain_count()` (property) | — |
| `main_chain_in_chains()` (property) | — |
| `prompt_tags()` (property) | — |
| `last_compared_at()` (property) | — |
| `is_top()` | — |
| `is_bottom()` | — |
| `get_links(better_than=False, worse_than=False)` | — |
| `get_chain(only_main=True)` | — |
| `get_position_in_chain()` | — |
| `get_component()` | — |
| `__repr__()` | — |


## `domain\graph\tests\__init__.py`

> Tests for graph/chain domain — ChainManager performance benchmarks, transitive reduction sorting, top/bottom node match with DB, cycle handling, and snapshot verification against known-optimal DAG.


## `domain\graph\tests\test_chain_manager.py`

> Check that bottom nodes are the last element in their main chain.

### Module-level functions

| Name | Description |
|---|---|
| `_build_manager(comparisons, all_filenames=None)` | — |
| `test_bottom_nodes_are_chain_last()` | Strictly assert that chains always start at tops and end at bottoms. |
| `test_performance_on_large_chains()` | Test that ChainManager processes a large dataset under 30 seconds. |
| `test_cycles_do_not_prevent_bottom_reachability()` | Test that cyclic paths still properly reach and end at the absolute bottom. |
| `test_transitive_reduction_sorting()` | Test that a>b, b>c, a>c correctly builds a single sorted chain a>b>c. |
| `test_uncompared_nodes_are_isolated_top_bottom()` | Test that uncompared images form single-node chains acting as both top and bottom. |
| `test_top_bottom_match_database_exactly()` | Test that computed tops/bottoms match expected: tops only have wins, bottoms only have losses. |
| `test_chain_snapshot_matches_known_optimal()` | Design a DAG with unambiguous optimal chains and assert exact output. |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `logging.getLogger(__name__)` |
| `DATASET_SIZE` | Set to 1000 by default. To stress test performance limits, try 10000 or 35000. |


## `domain\loading\__init__.py`

> Domain loading ports.

| Name | Description |
|---|---|
| `__all__` | Exports ['ModelLoader', 'BatchSizer', 'BatchSizerFactory', 'MapsProvider', 'TrainingLoader'] |
| `ModelLoader` | Re-exported through `__all__` |
| `BatchSizer` | Re-exported through `__all__` |
| `BatchSizerFactory` | Re-exported through `__all__` |
| `MapsProvider` | Re-exported through `__all__` |
| `TrainingLoader` | Re-exported through `__all__` |


## `domain\loading\ports.py`

> Port interfaces for loading-related services.

### Module-level constants

| Symbol | Description |
|---|---|
| `BatchSizerFactory` | `Callable[[str], BatchSizer]` |

### Class `ModelLoader` (Protocol)

| Name | Description |
|---|---|
| `load_vision_model(model_key)` | — |
| `get_model_info(model_key)` | — |
| `load_embedding_model()` | — |

### Class `BatchSizer` (Protocol)

| Name | Description |
|---|---|
| `get(width, height, rebuild, bound)` | — |

### Class `MapsProvider` (Protocol)

| Name | Description |
|---|---|
| `get_value(name, value)` | — |
| `add_value(name, value)` | — |
| `get_all_categories(name)` | — |
| `register_value(name, value)` | — |

### Class `TrainingLoader` (Protocol)

| Name | Description |
|---|---|
| `load_vectors()` | — |
| `load_scores()` | — |
| `load_training_model()` | — |
| `load_training_model_diagnostics()` | — |


## `domain\training\__init__.py`


## `domain\training\calibration.py`

### Module-level functions

| Name | Description |
|---|---|
| `_as_1d_float_array(values)` | — |
| `_strictly_increasing(values)` | — |
| `build_score_calibration(raw_scores, target_scores, num_points=257)` | Build a monotonic quantile-based score calibration table. |
| `extract_score_calibration(data)` | — |
| `apply_score_calibration(raw_scores, calibration)` | — |


## `domain\training\grid.py`

> LightGBM hyperparameter grid shared by model training and HPO.

### Module-level functions

| Name | Description |
|---|---|
| `around(label, val)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `grid_base` | step is relative percentage for float/int types |


## `domain\training\matrix_analysis.py`

> 2D Matrix Analysis for Text Data Parameters

### Class `MatrixAnalyzer`

| Name | Description |
|---|---|
| `__init__(scores, text_data, memory_limit=10000)` | — |
| `get_text_weight(original_text)` (staticmethod) | — |
| `_extract_all_params_from_record(record)` | — |
| `_add_param_from_value(key, value, params, prefix='')` | — |
| `build_matrix()` | — |
| `calculate_statistics(min_count=100)` | — |
| `export_to_json(output_path)` | — |
| `print_top_correlations(top_n=20)` | — |
| `get_matrix_size()` | — |
| `get_matrix_summary()` | — |


## `domain\training\parameter_analysis.py`

> Parameter Analysis Module

### Module-level functions

| Name | Description |
|---|---|
| `main()` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `SKLEARN_AVAILABLE` | `True` |
| `MATPLOTLIB_AVAILABLE` | `True` |

### Class `ParameterAnalyzer`

| Name | Description |
|---|---|
| `__init__(vectors_data, text_data, output_dir='output/analysis')` | — |
| `analyze_all()` | — |
| `analyze_parameter_pairs()` | — |
| `analyze_term_correlations()` | — |
| `_create_scatter(x, y, colors, name, xlabel, ylabel, normalize=False)` | — |
| `_create_2d_scatter(x, y, colors, name, xlabel, ylabel, zlabel)` | — |
| `_get_category_scores(categories)` | — |
| `_save_category_stats(filename, category_scores)` | — |
| `generate_report()` | — |


## `domain\training\plot.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `plt` | `plt` |

### Class `PlotManager`

> Manages all plotting functionality for model training and analysis.

| Name | Description |
|---|---|
| `_get_metric_direction(objective, metric)` (staticmethod) | — |
| `_prepare_finite_data(y, preds)` (staticmethod) | — |
| `_calculate_scatter_sizes(counts, min_size_px=1.0, max_size_px=800.0, power=0.5)` (staticmethod) | — |
| `_setup_scatter_axes(ax, y_min, y_max)` (staticmethod) | — |
| `plot_scatter_comparison(y_plot, p_plot, plot=True, min_size_px=10.0, max_size_px=100.0, power=0.5, label_threshold=10, title='Actual vs Predicted (sample)', x_label='Actual', y_label='Predicted')` (staticmethod) | — |
| `plot_scatter_comparison_continuous(y_plot, p_plot, plot=True, min_size_px=10.0, max_size_px=100.0, power=0.5, label_threshold=10, title='Actual vs Predicted (continuous)', x_label='Actual', y_label='Predicted', save_path=None, show=True)` (staticmethod) | — |
| `prepare_plot_data(y, preds)` (staticmethod) | — |
| `print_comparison_metrics(y, preds, metrics, objective=None, calibrated=False)` (staticmethod) | — |
| `compare_model_vs_data(x, y, training_loader, plot=True, limit=100, save_path=None, show=True)` (staticmethod) | — |
| `_plot_metric_on_axes(ax, metric_name, values, label, direction_higher)` (staticmethod) | — |
| `plot_metric(axes, current_metric, label='Valid')` (staticmethod) | — |
| `plot_loss_curve(result_metrics=None, save_path=None, show=True, training_loader=None)` (staticmethod) | — |
| `plot_score_distribution(y, save_path=None, show=True)` (staticmethod) | — |
| `plot_continuous_analysis(data_dict, group_name, x_label, y_label, cols=4, share_axes=True)` (staticmethod) | — |
| `plot_discrete_analysis(data_dict, group_name, x_label, y_label, cols=4)` (staticmethod) | — |
| `plot_aggregate_summary(data_dict, group_name, value_label, top_percent=0.1, limit=0, ascending=False)` (staticmethod) | — |
| `plot_individual_metrics(data_dict, cols=4, bins=10)` (staticmethod) | — |
| `plot_discrete_object_analysis(discrete_data, title_prefix='Discrete Analysis', cols=4)` (staticmethod) | — |
| `prepare_face_data(text_data, scores)` (staticmethod) | — |
| `plot_face_bbox(df_bbox)` (staticmethod) | — |
| `plot_positional_data(pos_data, group_name='Positional Data', cols=4, invert_y=True)` (staticmethod) | — |
| `plot_positional_bbox(pos_data, group_name='Bounding Boxes', cols=4, invert_y=True)` (staticmethod) | — |
| `plot_detection_presence(pose_score, no_pose_score, lh_score, no_lh_score, rh_score, no_rh_score)` (staticmethod) | — |
| `__init__(save_path=None, frequency=30, status_bar=None)` | — |
| `__call__(env)` | — |
| `plot_final_results()` | — |


## `domain\vectors\__init__.py`

> Vector/term extraction — prompt tokenization via depth-aware splitting, parenthetical weight parsing (term:1.2), stopword filtering with configurable connectors/splitters, deduplication keeping highest weight, and ExtractionResult dataclass with filtered/stripped/duplicate tracking.


## `domain\vectors\embedding_vector.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |

### Class `EmbeddingVector`

| Name | Description |
|---|---|
| `__init__(name, slot_size, model_loader)` | — |
| `parse_value_list(entries, alias=None)` | — |
| `create_vector_batch(current_batch)` | — |
| `create_vector_list(batch_size)` | — |
| `create_text_batch(current_batch)` | — |
| `create_text_list(batch_size)` | — |


## `domain\vectors\helpers.py`

### Module-level functions

| Name | Description |
|---|---|
| `l2_normalize_batch(vectors)` | — |
| `get_value_from_entry(entry, name, alias)` | — |


## `domain\vectors\image_vector.py`

### Module-level functions

| Name | Description |
|---|---|
| `scaled_batch_size(batch_size)` | — |
| `probe_bound_for_failed(failed_batch_size)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `sizeTuple` | `tuple[int, int]` |
| `vectorDict` | `dict[str, list[float]]` |
| `imagePathTuple` | `tuple[str, str]` |
| `imageTuple` | `tuple[str, Image.Image]` |

### Class `ImageVector`

| Name | Description |
|---|---|
| `__init__(name, model_key, slot_size, model_loader, batch_sizer_factory)` | — |
| `array_to_pil(arr)` | — |
| `prepare_image_batch(image)` | Convert various image inputs into a list of RGB PIL Images. |
| `create_image_vector_batch(current_batch)` | Encodes a batch of images into vectors. Assumes all images in the batch |
| `get_batch_size(width, height, rebuild, bound=None)` | — |
| `create_vector_list(entries, rebuild)` | — |
| `create_vector_list_from_paths(entries)` | Exact-size bucketing with controlled RAM and VRAM usage. |


## `domain\vectors\keypoint_vector.py`

### Class `KeypointVector`

> Per-instance keypoint vector (e.g. body pose landmarks).

| Name | Description |
|---|---|
| `__init__(name)` | — |
| `_config_index()` | — |
| `_grow(needed)` | — |
| `parse_value_list(entries, add_new_values, alias)` | — |
| `create_vector_list()` | — |

| Class constant | Description |
|---|---|
| `PER_UNIT` | `4` |
| `KEYS` | `('x', 'y', 'z', 'visibility')` |


## `domain\vectors\map_vector.py`

### Class `MapVector`

> Categorical map with float weights.

| Name | Description |
|---|---|
| `__init__(name, maps_provider)` | — |
| `_config_index()` | — |
| `_maybe_grow(size)` | — |
| `_normalize(value)` | — |
| `parse_value_list(entries, add_new_values, alias)` | — |
| `create_vector_list()` | — |


## `domain\vectors\number_vector.py`

### Class `IntVector`

| Name | Description |
|---|---|
| `__init__(name, max_normalization)` | — |
| `parse_value_list(entries, alias)` | — |
| `create_vector_list()` | — |

### Class `FloatVector`

| Name | Description |
|---|---|
| `__init__(name, max_normalization)` | — |
| `parse_value_list(entries, alias)` | — |
| `create_vector_list()` | — |


## `domain\vectors\person_map_vector.py`

### Class `PersonMapVector`

> Per-person categorical map (e.g. age / gender / race).

| Name | Description |
|---|---|
| `__init__(name, maps_provider)` | — |
| `_config_index()` | — |
| `_per_unit()` | — |
| `_grow(needed)` | — |
| `parse_value_list(entries, add_new_values, alias)` | — |
| `create_vector_list()` | — |


## `domain\vectors\position_vector.py`

### Class `PositionVector`

> Per-instance positional vector (e.g. face bounding box).

| Name | Description |
|---|---|
| `__init__(name)` | — |
| `_config_index()` | — |
| `_grow(needed)` | — |
| `parse_value_list(entries, add_new_values, alias)` | — |
| `create_vector_list()` | — |

| Class constant | Description |
|---|---|
| `PER_UNIT` | `5` |
| `KEYS` | `('x', 'y', 'width', 'height', 'confidence')` |


## `domain\vectors\terms.py`

### Module-level functions

| Name | Description |
|---|---|
| `extract_weight_from_paren(text)` | Extracts content and weight from (term:weight) or (term). |
| `tokenize_by_depth(text, splitters)` | Splits text by splitters and parenthetical boundaries, respecting nesting depth. |
| `clean_term(term)` | Normalizes string content and removes technical artifacts. |
| `filter_terms(terms, connectors, splitters)` | Removes standard stopwords unless they are protected by the user's sets. |
| `deduplicate_terms(terms)` | Merges duplicate terms, retaining the highest weight found. |
| `_extract_recursive(text, current_weight, splitters)` | Handles the heavy lifting of nesting and weight multiplication. |
| `extract_terms(text, connectors=('and', 'or'), splitters=(',', 'but', 'not'))` | The main entry point for processing prompt text into weighted vectors. |

### Module-level constants

| Symbol | Description |
|---|---|
| `WeightedTerm` | `tuple[str, float, int]` |

### Class `ExtractionResult`

| Field | Description |
|---|---|
| `terms` | — |
| `raw` | — |
| `filtered_out` | — |
| `stripped` | — |
| `duplicates` | — |


## `domain\vectors\tests\__init__.py`

> Tests for vector/term extraction — parametrized tests for extract_terms with varied prompt patterns, clean_term normalization, deduplication weighting logic, filter stopword removal, and weight-from-parenthesis parsing.


## `domain\vectors\tests\test_terms.py`

### Module-level functions

| Name | Description |
|---|---|
| `test_extract_terms_variations(input_text, expected_output)` | — |
| `test_custom_splitters()` | — |
| `test_custom_connectors()` | — |
| `test_clean_term(input_term, expected)` | Verifies that strings are normalized correctly. |
| `test_deduplicate_terms_logic()` | Verifies that the highest weight is kept for duplicate terms. |
| `test_filter_terms_with_connectors()` | Verifies stop-words are removed unless they are in connectors/splitters. |
| `test_extract_weight_from_paren(text, expected)` | Verifies weight extraction from parenthetical strings. |

### Module-level constants

| Symbol | Description |
|---|---|
| `long_text_test_list` | `[]` |


## `application\__init__.py`

> Application layer — use-case orchestration connecting domain logic to infrastructure: CrystalGraph service, DTOs for API shaping, and port interfaces for dependency inversion.


## `application\analysis\__init__.py`


## `application\analysis\run_matrix_analysis.py`

### Module-level functions

| Name | Description |
|---|---|
| `run_matrix_analysis()` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |


## `application\analysis\run_parameter_analysis.py`

### Module-level functions

| Name | Description |
|---|---|
| `run_parameter_analysis()` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |


## `application\analysis\run_stats.py`

### Module-level functions

| Name | Description |
|---|---|
| `_distribute(values, bins)` | — |
| `run_stats(graph)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |


## `application\data_transform\__init__.py`

> application.data_transform package for comfyui_image_scorer.


## `application\data_transform\config\__init__.py`


## `application\data_transform\config\maps.py`

### Module-level functions

| Name | Description |
|---|---|
| `register_map_values(processed_data, maps_provider)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |


## `application\data_transform\prepare_data.py`

### Module-level functions

| Name | Description |
|---|---|
| `build_split_files(limit, model_loader, batch_sizer_factory, maps_provider)` | — |
| `build_full_files(model_loader, batch_sizer_factory, maps_provider)` | — |
| `run_rebuild_scores_only(graph)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |


## `application\hyperparameters\__init__.py`

> application.hyperparameters package for comfyui_image_scorer.


## `application\hyperparameters\hyperparameter_optimizer.py`

### Module-level functions

| Name | Description |
|---|---|
| `generate_random_config()` | — |
| `generate_fastest_setup()` | Generates a config likely to be fast (fewer estimators, shallow trees). |
| `generate_slowest_setup()` | Generates a config likely to be slow (max estimators, deep trees). |
| `crossover_config(cfg1, cfg2)` | Merge two configs into a new child by picking each key from one parent. |
| `_load_state()` | — |
| `_save_state(state)` | — |
| `reset_hyperparameters()` | — |
| `load_training_data(filter_comparisons, training_loader, model_trainer)` | Load keyed vectors/scores and compress unused features. When |
| `_evaluate_config(cfg, X, y, model_trainer)` | — |
| `_run_step_on_config(cfg, used_keys, X, y, max_combos, model_trainer)` | — |
| `hpo_cycle(X, y, model_trainer, optimization_steps=100, max_combos=4, cycle=0)` | — |
| `run_hpo_cycles(cycles=None, optimization_steps=None, max_combos=None, training_loader=None, model_trainer=None)` | Run multiple HPO cycles. Each cycle runs optimization_steps steps |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `NUM_CONFIGS` | `5` |
| `_hpo_running` | be started explicitly and may not be invoked more than once at a time. |


## `application\services\__init__.py`

> Application services - ScoringService: full scoring workflow encapsulating image analysis, vector creation, feature filtering, model prediction, and score calibration; CrystalGraph: high-level graph API orchestrating ChainManager + repositories.


## `application\services\graph_service.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `NodeTuple` | Type aliases for chain mapping structures |
| `ChainTuple` | Type aliases for chain mapping structures |
| `ChainDict` | `dict[int, ChainTuple]` |

### Class `CrystalGraph`

> Main graph API. All access through get_* methods returning proxy objects.

| Name | Description |
|---|---|
| `__init__(image_repo=None, comparison_repo=None)` | — |
| `get_node_chain_length(filename)` | — |
| `get_main_chain_member_count(chain_id)` | Return how many nodes have ``chain_id`` as their main chain. |
| `rebuild_from_database(images=None, comparisons=None)` | — |
| `apply_comparison(winner, loser)` | — |
| `is_cache_stale()` | — |
| `get_node(node_id=None)` | — |
| `get_all_nodes(only_top=False, only_bottom=False)` | — |
| `get_chain(node_id=None, chain_id=None)` | — |
| `get_all_chains(min_length=0, sort_order='desc')` | — |
| `get_component(node_id=None, component_id=None, chain_id=None)` | — |
| `get_all_components()` | — |
| `get_all_links()` | — |
| `get_graph_stats()` | — |
| `are_in_same_path(img1, img2)` | — |
| `get_chains_map()` | — |


## `application\services\image_processor.py`

> Image processor - discovery, initialization, and rebuild flow.

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |

### Class `PathOps`

> Infrastructure file/path operations injected by the composition root.

| Field | Description |
|---|---|
| `ranked_root` | — |
| `compute_path` | — |
| `sync_metadata` | — |
| `clear_folder_cache` | — |
| `prewarm_folder_cache` | — |
| `deduplicate_scored` | — |
| `cleanup_orphans` | — |

### Class `ImageProcessor`

> Process uninitialized images with parallel workers.

| Name | Description |
|---|---|
| `__init__(max_workers, graph, path_ops)` | — |
| `_extract_prompt_tags(data)` | — |
| `clean_json_metadata(json_data, default_score, filename)` | — |
| `process_image_file(image_path)` | Process a single raw image file into the ranked tree. |
| `sync_processed_images_from_db()` | — |
| `get_fast_total_count(source_dir)` | — |
| `process_next_batch(source_dir, batch_size)` | — |
| `rebuild_database_from_ranked()` | Rebuild or repair the ranking database from ranked files and companion JSON. |
| `_recompute_ratings_from_database_history()` | — |
| `reorganize_folder_structure()` | — |
| `clear_old_cache(force)` | — |


## `application\services\scoring_service.py`

### Class `ScoringService`

> Application service that encapsulates the full scoring workflow.

| Name | Description |
|---|---|
| `__init__(model_loader, batch_sizer, training_loader, model_trainer, maps_provider, *, batch_size=10)` | — |
| `score(image, threshold, positive, negative, steps, cfg, sampler, scheduler, model_name, lora_name, lora_strength, min_images=1, max_images=10)` | — |
| `_predict_scores(model, filtered_vectors)` | — |


## `application\services\vector_list.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |

### Class `VectorList`

| Name | Description |
|---|---|
| `__init__(raw_data, read_only, model_loader, batch_sizer_factory, maps_provider)` | — |
| `configure_sorted_vectors()` | — |
| `_exclude_present_entry(current_vector)` | — |
| `_exclude_present_image_path(current_vector)` | — |
| `create_vectors()` | — |
| `validate_and_convert(data, name, target_size)` | — |
| `filter_missing_vectors()` | — |
| `join_vectors()` | — |
| `convert_text_list(clean_arrays, current_list, name)` | — |
| `join_text_data()` | — |
| `update_lists()` | — |
| `load_split_files()` | — |
| `export_split_files()` | — |

| Class constant | Description |
|---|---|
| `_IMAGE` | `'image'` |
| `_INT` | `'int'` |
| `_FLOAT` | `'float'` |
| `_MAP` | `'map'` |
| `_EMBEDDING` | `'embedding'` |
| `_POSITION` | `'position'` |
| `_KEYPOINT` | `'keypoint'` |
| `_PERSON_MAP` | `'person_map'` |


## `adapters\__init__.py`

> Adapters — external interface layer connecting the application to ComfyUI (node registration), CLI (command entry), web server (REST API + frontend assets), and frontend JS/CSS/HTML assets.


## `adapters\analyze\__init__.py`

> Analyze adapter — frontend JS/CSS assets for the analysis/dashboard tab in the web UI: score distribution charts, trend graphs, and quality metrics.


## `adapters\analyze\frontend\__init__.py`

> Analyze frontend — static assets (JS, CSS, HTML) for the analysis visualization dashboard: statistical plots, trend lines, and data tables.


## `adapters\build\__init__.py`

> Build adapter — frontend JS/CSS assets for the data preparation pipeline UI: split/full vector generation and cleanup controls.


## `adapters\build\frontend\__init__.py`

> Build frontend — static assets for data preparation controls: split/full vector generation, limits, and cleanup.


## `adapters\cli\__init__.py`

> CLI adapter — command-line entry point (main function) for python -m invocation: sys.path setup, argument parsing, and application orchestration.


## `adapters\cli\commands\__init__.py`

> CLI commands — sub-command dispatch and implementation for CLI-driven workflows (scoring, ranking, export, cleanup), organized as pluggable sub-commands (future).


## `adapters\cli\commands\database.py`

### Module-level functions

| Name | Description |
|---|---|
| `cleanup(deps)` | — |
| `rebuild(deps)` | — |
| `recalculate(deps)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |


## `adapters\cli\commands\server.py`

### Module-level functions

| Name | Description |
|---|---|
| `run_server(host, port, debug)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `_MODULE_ROOT` | `Path(__file__).resolve().parents[3]` |
| `_SERVER_ENTRY` | `'comfyui_image_scorer.adapters.server.main'` |


## `adapters\cli\commands\training.py`

### Module-level functions

| Name | Description |
|---|---|
| `train_model(deps)` | — |
| `run_hpo(deps, cycles, optimization_steps, max_combos)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |


## `adapters\cli\commands\vectors.py`

### Module-level functions

| Name | Description |
|---|---|
| `run_split_vectors(limit, batch, deps)` | — |
| `run_full_vectors(deps)` | — |
| `run_scores(deps)` | — |
| `run_all(limit, batch, deps)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |


## `adapters\cli\deps.py`

> CLI composition root - builds injected dependencies for the CLI commands.

### Module-level functions

| Name | Description |
|---|---|
| `build_cli_deps()` | — |

### Class `CLIDeps`

| Field | Description |
|---|---|
| `image_repo` | — |
| `comparison_repo` | — |
| `processor` | — |
| `model_loader` | — |
| `batch_sizer_factory` | — |
| `maps_provider` | — |
| `training_loader` | — |
| `model_trainer` | — |
| `vacuum_database` | — |
| `deduplicate_scored` | — |
| `cleanup_orphans` | — |
| `download_configured_models` | — |
| `download_mediapipe_models` | — |
| `set_hub_offline` | — |


## `adapters\cli\main.py`

### Module-level functions

| Name | Description |
|---|---|
| `_add_build_parser(subparsers)` | — |
| `_add_training_parser(subparsers)` | — |
| `_add_database_parser(subparsers)` | — |
| `_add_files_parser(subparsers)` | — |
| `_add_analyze_parser(subparsers)` | — |
| `main()` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |


## `adapters\comfyui\__init__.py`

> ComfyUI adapter — exports NODE_CLASS_MAPPINGS and NODE_DISPLAY_NAME_MAPPINGS dicts for automatic custom-node registration when ComfyUI loads this package.

| Name | Description |
|---|---|
| `__all__` | Exports ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS'] |
| `NODE_CLASS_MAPPINGS` | Re-exported through `__all__` |
| `NODE_DISPLAY_NAME_MAPPINGS` | Re-exported through `__all__` |


## `adapters\comfyui\input_adapters\__init__.py`

> Input adapters — ComfyUI input-type converters and validation helpers for custom node sockets: image, conditioning, latent, and primitive type adapters (future).


## `adapters\comfyui\node_registry.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `NODE_CLASS_MAPPINGS` | `{'AestheticScore': AestheticScoreNode}` |
| `NODE_DISPLAY_NAME_MAPPINGS` | `{'AestheticScore': 'Aesthetic Score'}` |


## `adapters\comfyui\nodes\__init__.py`

> ComfyUI node definitions — custom node implementations: aesthetic scoring, ranking/graph visualization, gallery browsing, and map/heatmap display.


## `adapters\comfyui\nodes\aesthetic_score\__init__.py`

| Name | Description |
|---|---|
| `__all__` | Exports ['AestheticScoreNode'] |
| `AestheticScoreNode` | Re-exported through `__all__` |


## `adapters\comfyui\nodes\aesthetic_score\node.py`

### Class `AestheticScoreNode`

| Name | Description |
|---|---|
| `__init__()` | — |
| `INPUT_TYPES()` (classmethod) | — |
| `calculate_score(image, threshold, positive, negative, steps, cfg, sampler, scheduler, model_name, lora_name, lora_strength, min_images=1, max_images=10)` | — |

| Class constant | Description |
|---|---|
| `RETURN_TYPES` | `('IMAGE', 'IMAGE', 'BOOLEAN', 'LIST')` |
| `RETURN_NAMES` | `('images', 'discarded images', 'Available', 'score')` |
| `FUNCTION` | `'calculate_score'` |
| `CATEGORY` | `'Scoring'` |


## `adapters\comfyui\output_adapters\__init__.py`

> Output adapters — ComfyUI output-type formatters and serializers for custom node return values: score dicts, ranking data, graph structures (future).


## `adapters\comfyui\services.py`

> ComfyUI node wiring - builds ScoringService from infrastructure singletons.

| Name | Description |
|---|---|
| `__all__` | Exports ['get_scoring_service', 'verify_models_present'] |
| `get_scoring_service` | Re-exported through `__all__` |
| `verify_models_present` | Re-exported through `__all__` |

### Module-level functions

| Name | Description |
|---|---|
| `get_scoring_service()` | — |


## `adapters\comparison\__init__.py`

> Comparison adapter — frontend JS/CSS assets for the pairwise comparison UI tab: image A/B display, rating controls, and progress tracking.


## `adapters\comparison\frontend\__init__.py`

> Comparison frontend — static assets for the image comparison workflow UI: side-by-side or overlay comparison, vote recording, and batch navigation.


## `adapters\database\__init__.py`

> Database adapter — frontend JS/CSS assets for the database maintenance and file management UI.


## `adapters\database\frontend\__init__.py`

> Database frontend — static assets for database maintenance and file management: rebuild, recalculate, cleanup, downloads.


## `adapters\gallery\__init__.py`

> Gallery adapter — frontend JS/CSS assets for the image gallery browsing tab: grid/thumbnail display, scoring badges, and filter controls.


## `adapters\gallery\frontend\__init__.py`

> Gallery frontend — static assets for image gallery display: virtual-scrolled grid, score/rank overlays, search/filter sidebar, and batch selection.


## `adapters\maps2\__init__.py`

> Maps2 adapter — frontend JS/CSS assets for map/graph visualization tab (v2): redesigned graph topology, score heatmaps, and chain/component overlays.


## `adapters\maps2\frontend\__init__.py`

> Maps2 frontend — static assets for graph topology and score map visualization: DAG rendering, node/link diagrams, and interactive zooming (version 2).


## `adapters\maps2\frontend\graph_map\__init__.py`

> Maps2 frontend graph-map — rendering components for directed-graph map visualization: node positioning, edge routing, and interactive selection (version 2).


## `adapters\maps\__init__.py`

> Maps adapter — frontend JS/CSS assets for map/graph visualization tab (v1): graph topology, score heatmaps, and chain/component overlays.


## `adapters\maps\frontend\__init__.py`

> Maps frontend v1 — static assets for graph topology and score map visualization: DAG rendering, node/link diagrams, and interactive zooming (version 1).


## `adapters\maps\frontend\graph_map\__init__.py`

> Maps frontend graph-map v1 — rendering components for directed-graph map visualization: node positioning, edge routing, and interactive selection (version 1).


## `adapters\server\__init__.py`

> Server adapter — web server providing REST API endpoints and static asset serving for the web UI.


## `adapters\server\deps.py`

> Server dependency container - constructed by the adapters/server composition root.

### Module-level functions

| Name | Description |
|---|---|
| `get_server_deps()` | — |
| `to_cli_deps()` | — |

### Class `ServerDeps`

| Field | Description |
|---|---|
| `image_repo` | — |
| `comparison_repo` | — |
| `path_resolver` | — |
| `path_ops` | — |
| `graph` | — |
| `processor` | — |
| `model_loader` | — |
| `batch_sizer_factory` | — |
| `maps_provider` | — |
| `training_loader` | — |
| `model_trainer` | — |
| `vacuum_database` | — |
| `deduplicate_scored` | — |
| `cleanup_orphans` | — |
| `download_configured_models` | — |
| `download_mediapipe_models` | — |
| `set_hub_offline` | — |


## `adapters\server\endpoints\__init__.py`

> Server endpoints — HTTP request handler implementations for API operations: build pipeline, training, database maintenance, analysis, file management, ranking, gallery, and maps.


## `adapters\server\endpoints\analyze.py`

> Analyze API - endpoints for statistics, parameter analysis, and matrix analysis.

### Module-level functions

| Name | Description |
|---|---|
| `stats()` | — |
| `analyze_parameters()` | — |
| `analyze_matrix()` | — |
| `register_analyze_routes(app, deps)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `analyze_bp` | `Blueprint('analyze', __name__, url_prefix='/api/analyze')` |
| `logger` | `get_logger(__name__)` |


## `adapters\server\endpoints\build.py`

> Build API - endpoints for the data preparation pipeline.

### Module-level functions

| Name | Description |
|---|---|
| `prepare()` | — |
| `delete_vectors()` | Delete the full vector files from disk, keeping the split files intact. |
| `register_build_routes(app, deps)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `build_bp` | `Blueprint('build', __name__, url_prefix='/api/build')` |
| `logger` | `get_logger(__name__)` |
| `_PREPARE_MODES` | `('split', 'full', 'all')` |


## `adapters\server\endpoints\comparison.py`

> Ranking API v2 endpoints.

### Module-level functions

| Name | Description |
|---|---|
| `_get_processor()` | — |
| `_get_level_progress_stats(all_images)` | — |
| `get_ranking_config()` | — |
| `get_ranking_phases()` | — |
| `get_status()` | — |
| `get_next_pair()` | — |
| `reset_ranking_queue()` | — |
| `skip_image()` | — |
| `submit_comparison()` | — |
| `sync_all_to_json()` | — |
| `register_ranking_routes(app, deps)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `ranking_bp` | `Blueprint('ranking_v2', __name__, url_prefix='/api/ranking')` |
| `logger` | `get_logger(__name__)` |


## `adapters\server\endpoints\database.py`

> Database endpoints - API routes for maintenance.

### Module-level functions

| Name | Description |
|---|---|
| `rebuild_database()` | — |
| `recalculate_ratings()` | — |
| `clean_database()` | — |
| `register_database_routes(app, deps)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `database_bp` | `Blueprint('database', __name__, url_prefix='/api/database')` |


## `adapters\server\endpoints\files.py`

> Files API - endpoints for file management operations.

### Module-level functions

| Name | Description |
|---|---|
| `delete_models()` | — |
| `delete_maps()` | — |
| `delete_downloaded_models()` | — |
| `download_models()` | — |
| `cleanup()` | — |
| `register_files_routes(app, deps)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `files_bp` | `Blueprint('files', __name__, url_prefix='/api/files')` |
| `logger` | `get_logger(__name__)` |


## `adapters\server\endpoints\gallery.py`

> Gallery API - endpoints for viewing and filtering ranked images.

### Module-level functions

| Name | Description |
|---|---|
| `list_images()` | — |
| `get_image_info(filename)` | — |
| `search_images()` | — |
| `get_image_history(filename)` | — |
| `register_gallery_routes(app, deps)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `gallery_bp` | `Blueprint('gallery_v2', __name__, url_prefix='/api/gallery')` |
| `logger` | `get_logger(__name__)` |


## `adapters\server\endpoints\maps.py`

> Maps API - endpoints for chain visualizations (graph data).

### Module-level functions

| Name | Description |
|---|---|
| `get_graph_data()` | — |
| `register_maps_routes(app, deps)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `maps_bp` | `Blueprint('maps_v2', __name__, url_prefix='/api/maps')` |
| `logger` | `get_logger(__name__)` |


## `adapters\server\endpoints\training.py`

> Training & Hyperparameters API - endpoints for model training and HPO.

### Module-level functions

| Name | Description |
|---|---|
| `train()` | — |
| `hpo()` | — |
| `register_training_routes(app, deps)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `training_bp` | `Blueprint('training', __name__, url_prefix='/api/training')` |
| `logger` | `get_logger(__name__)` |


## `adapters\server\frontend\__init__.py`

> Server frontend — static web assets (CSS, HTML, JS) served by the server adapter for the browser-based management UI.


## `adapters\server\main.py`

> Main server - Flask application for ranking system.

### Module-level functions

| Name | Description |
|---|---|
| `serve_index()` | — |
| `serve_css(filename)` | — |
| `serve_js(filename)` | — |
| `serve_section_static(section, filename)` | — |
| `serve_ranked_image(filepath)` | — |
| `serve_image_by_name(filename)` | — |
| `serve_image_alias(filename)` | — |
| `catch_api_404(path)` | — |
| `serve_html(filename)` | — |
| `not_found(_e)` | — |
| `server_error(e)` | — |
| `scanner_task(img_root)` | — |
| `startup_worker()` | — |
| `init_ranking_system()` | — |
| `main()` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `image_repo` | `SQLiteImagesRepository()` |
| `comparison_repo` | `SQLiteComparisonsRepository()` |
| `graph` | `CrystalGraph(image_repo=image_repo, comparison_repo=comparison_repo)` |
| `path_ops` | `PathOps(ranked_root=get_ranked_root, compute_path=compute_path_from_filename, sync_metadata=sync_image_metadata_to_json, clear_folder_cache=clear_folder_cache, prewarm_folder_cache=prewarm_folder_cache, deduplicate_scored=deduplicate_scored, cleanup_orphans=cleanup_orphans)` |
| `image_processor` | `ImageProcessor(max_workers=int(config['ranking']['max_workers']), image_repo=image_repo, comparison_repo=comparison_repo, graph=graph, path_ops=path_ops)` |
| `deps` | `ServerDeps(image_repo=image_repo, comparison_repo=comparison_repo, path_resolver=_PathResolverAdapter(), path_ops=path_ops, graph=graph, processor=image_processor, model_loader=model_loader, batch_sizer_factory=BatchSizer, maps_provider=maps_list, training_loader=training_loader, model_trainer=model_trainer, vacuum_database=vacuum_database, cleanup_orphans=cleanup_orphans, deduplicate_scored=deduplicate_scored, download_configured_models=download_configured_models, download_mediapipe_models=download_mediapipe_models)` |
| `app` | `Flask(__name__, static_folder=None)` |
| `SECTION_FRONTENDS` | `{'comparison': Path(__file__).parent.parent / 'comparison' / 'frontend', 'gallery': Path(__file__).parent.parent / 'gallery' / 'frontend', 'maps': Path(__file__).parent.parent / 'maps' / 'frontend', 'maps2': Path(__file__).parent.parent / 'maps2' / 'frontend', 'database': Path(__file__).parent.parent / 'database' / 'frontend', 'build': Path(__file__).parent.parent / 'build' / 'frontend', 'training': Path(__file__).parent.parent / 'training' / 'frontend', 'analyze': Path(__file__).parent.parent / 'analyze' / 'frontend'}` |
| `SERVER_FRONTEND` | `Path(__file__).parent / 'frontend'` |
| `scanner_thread` | `None` |

### Class `_PathResolverAdapter`

| Name | Description |
|---|---|
| `sync_image_metadata_to_json(filename, score, rating_mu, rating_sigma, comparison_count, all_comparisons=None)` | — |


## `adapters\training\__init__.py`

> Training adapter — frontend JS/CSS assets for the training and HPO UI: train top model and hyperparameter optimization.


## `adapters\training\frontend\__init__.py`

> Training frontend — static assets for training controls: train top model and HPO cycle runs.


## `infrastructure\__init__.py`

> Infrastructure layer — persistence (database, comparisons_repository, images_repository).


## `domain\ports\__init__.py`

> Domain ports for cross-cutting infrastructure capabilities.


## `domain\ports\cache.py`

> Cache port — injected key/value cache for temporary execution state.

### Class `CacheProvider` (Protocol)

| Name | Description |
|---|---|
| `get(key)` | — |
| `set(key, value)` | — |
| `invalidate(key)` | — |
| `clear()` | — |


## `infrastructure\cache\__init__.py`

> Infrastructure cache implementations.


## `infrastructure\cache\memory_cache.py`

### Class `InMemoryCache` (CacheProvider)

| Name | Description |
|---|---|
| `__init__(default_ttl=None, max_bytes=None)` | — |
| `get(key)` | — |
| `set(key, value)` | — |
| `invalidate(key)` | — |
| `clear()` | — |


## `infrastructure\external_services\__init__.py`

> External services — API clients for remote model inference, cloud storage, and third-party data sources (future).


## `infrastructure\external_services\mediapipe_models.py`

### Module-level functions

| Name | Description |
|---|---|
| `download_mediapipe_models()` | — |
| `_download_to(url, dest, key)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |


## `infrastructure\loading\__init__.py`


## `infrastructure\loading\maps_loader.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `AGE_CATEGORIES` | (FairFace age bins) and the metric names emitted by image_analysis.py. |
| `GENDER_CATEGORIES` | `['Female', 'Male']` |
| `RACE_CATEGORIES` | `['Black', 'East Asian', 'Indian', 'Latino_Hispanic', 'Middle Eastern', 'Southeast Asian', 'White']` |
| `ANALYSIS_CATEGORIES` | `['contrast', 'sharpness', 'noise_score', 'colorfulness', 'artifact_score', 'edge_density', 'texture_lbp']` |
| `maps_list` | `MapsLoader()` |

### Class `MapsLoader`

| Name | Description |
|---|---|
| `__init__()` | — |
| `get_all_categories(name)` | — |
| `register_value(name, value)` | Idempotently ensure ``value`` (and its sub-keys for dict/list values) |
| `add_value(name, value)` | return index of the new added value to the current map |
| `get_value(name, value)` | get a value from the current map |
| `_save_single_map(name)` | — |
| `_load_single_map(name)` | — |
| `load_maps()` | — |


## `infrastructure\loading\training_loader.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `training_loader` | `TrainingLoader(True)` |

### Class `TrainingLoader`

| Name | Description |
|---|---|
| `__init__(use_cache)` | — |
| `_reset_models()` | — |
| `remove_training_models()` | — |
| `load_vectors()` | Load vectors keyed by filename. |
| `load_vectors_array()` | — |
| `_load_vectors_from_jsonl()` | — |
| `_load_vectors_from_npz()` | — |
| `_save_vectors_to_npz(keyed)` | — |
| `load_scores()` | Load scores keyed by filename. |
| `load_scores_array()` | — |
| `_load_scores_from_jsonl()` | — |
| `_load_scores_from_npz()` | — |
| `_save_scores_to_npz(keyed)` | — |
| `load_comparison_rows()` | Load ordered comparison rows (filename_a, filename_b, winner, id). |
| `load_comparison_counts()` | Return per-filename comparison counts derived from the rows. |
| `_load_comparisons_from_npz()` | — |
| `_save_comparisons_to_npz(rows)` | — |
| `load_feature_rule()` | — |
| `save_feature_rule(kept_indices)` | — |
| `load_comparison_rule(threshold)` | Return the cached subset rule for this threshold. |
| `save_comparison_rule(threshold, rule)` | — |
| `load_interaction_data()` | — |
| `save_interaction_data(x, top_k_indices_local)` | — |
| `_normalize(val)` | — |
| `load_training_model_diagnostics()` | — |
| `load_training_model()` | — |
| `save_training_model(model, additional_data)` | Save a trained model to disk. |


## `infrastructure\ml_models\__init__.py`


## `infrastructure\ml_models\batch_sizer.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |

### Class `HistoryEntry`

| Field | Description |
|---|---|
| `batch_size` | — |
| `delta_memory` | — |
| `timestamp` | — |

### Class `ProfileData`

| Field | Description |
|---|---|
| `model_name` | — |
| `device_name` | — |
| `device_id` | — |
| `total_memory` | — |
| `model_memory_bytes` | — |
| `fixed_overhead` | — |
| `pixel_cost` | — |
| `r_squared` | — |
| `history` | — |

### Class `BatchSizer`

| Name | Description |
|---|---|
| `__init__(model_key)` | — |
| `_ensure_session_profiled()` | — |
| `_resolution_key(width, height)` (staticmethod) | — |
| `get(width, height, rebuild, bound=None)` | — |
| `_profile_new_resolution(width, height, rebuild, bound=None)` | — |
| `_evaluate_candidate(*, model, profile, key, candidate, width, height, device_id)` | — |
| `_fit_model()` | — |
| `_save_cache()` | — |


## `infrastructure\ml_models\model_loader.py`

### Module-level functions

| Name | Description |
|---|---|
| `_missing_model_error(description)` | — |
| `_face_attributes_checkpoint_path(name)` | — |
| `set_hub_offline(enabled)` | Flip HF hub offline mode after the import-time constants were mirrored. |
| `verify_models_present()` | — |
| `download_configured_models()` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `model_loader` | `ModelLoader()` |

### Class `MultiTaskClipVisionModel` (nn.Module)

| Name | Description |
|---|---|
| `__init__(num_labels)` | — |
| `forward(pixel_values)` | — |

| Class constant | Description |
|---|---|
| `_VISION_CONFIG` | `CLIPVisionConfig(hidden_size=1024, intermediate_size=4096, num_attention_heads=16, num_hidden_layers=24, patch_size=14, image_size=224)` |

### Class `ModelLoader`

| Name | Description |
|---|---|
| `__init__()` | — |
| `_select_transform(name)` (staticmethod) | — |
| `load_vision_model(model_key='convnext')` | — |
| `get_model_info(model_key)` | — |
| `load_embedding_model()` | — |
| `load_hf_vision_model(model_key)` | — |
| `_load_hf_vision_model_impl(model_key)` | — |

| Class constant | Description |
|---|---|
| `_IMAGENET_NORM` | `transforms.Compose([transforms.ToTensor(), transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225))])` |
| `_CLIP_NORM` | `transforms.Compose([transforms.ToTensor(), transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5))])` |


## `infrastructure\ml_models\training\__init__.py`


## `infrastructure\ml_models\training\model_trainer.py`

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `model_trainer` | `ModelTrainer()` |

### Class `ModelTrainer`

| Name | Description |
|---|---|
| `__init__()` | — |
| `r2_metric(y_true, y_pred)` | Custom R2 metric for LightGBM evaluation. |
| `_pairwise_accuracy(y_true, y_pred)` (staticmethod) | Compute pairwise accuracy for flattened 2-row comparison groups. |
| `_build_score_calibration(X)` | Build a fixed raw->score calibration for lambdarank models. |
| `create_training_model(config_dict)` | — |
| `create_callbacks(progress_bar)` | — |
| `create_metrics(y_test, y_pred, training_time)` | — |
| `train_model_pairs(config_dict, X, comparisons, index_list)` | — |
| `train_model(config_dict, X, y)` | — |


## `infrastructure\ml_models\training\pair_data.py`

### Module-level functions

| Name | Description |
|---|---|
| `load_comparison_records()` | — |
| `build_pairwise_dataset(x, index_list, comparisons)` | — |


## `infrastructure\persistence\__init__.py`

> Persistence — SQLite connection management (database.py), comparisons CRUD (comparisons_repository.py), and images repository (images_repository.py).


## `infrastructure\persistence\cleanup_orphans.py`

> Cleanup orphaned image / JSON companion files inside the scored folder.

### Module-level functions

| Name | Description |
|---|---|
| `_walk_all_files(root)` | — |
| `_scored_root_files(root)` | — |
| `cleanup_orphans(root=None)` | — |
| `main()` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `IMAGE_EXTENSIONS` | `{'.png', '.jpg', '.jpeg', '.webp'}` |


## `infrastructure\persistence\comparisons_repository.py`

> Comparisons table operations.

### Module-level functions

| Name | Description |
|---|---|
| `_canonicalize_pair(filename_a, filename_b)` | — |
| `_safe_parse_timestamp(timestamp)` | — |
| `add_historical_comparison(filename_a, filename_b, winner, timestamp, weight=1.0, transitive_depth=0)` | Insert one historical comparison row if an exact copy does not already exist. |
| `add_comparison(filename_a, filename_b, winner, weight=1.0, transitive_depth=0, timestamp=None)` | Record a comparison result. |
| `comparison_exists_for_pair(filename_a, filename_b)` | — |
| `clear_all_comparisons()` | — |
| `get_total_comparisons()` | — |
| `get_skipped_comparison_count()` | — |
| `get_all_comparisons(weight=None)` | — |
| `get_images_with_only_wins()` | — |
| `get_images_with_only_losses()` | — |
| `clean_comparisons()` | Clean imported comparison history before any rating replay. |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |

### Class `SQLiteComparisonsRepository`

> Injected implementation of the ComparisonRepository port.

| Name | Description |
|---|---|
| `add_comparison(filename_a, filename_b, winner, weight=1.0, transitive_depth=0, timestamp=None)` | — |
| `add_historical_comparison(filename_a, filename_b, winner, timestamp, weight=1.0, transitive_depth=0)` | — |
| `comparison_exists_for_pair(filename_a, filename_b)` | — |
| `get_all_comparisons(weight=None)` | — |
| `get_total_comparisons()` | — |
| `get_skipped_comparison_count()` | — |
| `clean_comparisons()` | — |
| `get_images_with_only_wins()` | — |
| `get_images_with_only_losses()` | — |
| `clear_all_comparisons()` | — |


## `infrastructure\persistence\database.py`

> Database schema definitions and connection management.

### Module-level functions

| Name | Description |
|---|---|
| `get_db_connection()` | Create and return SQLite connection with row factory. |
| `_check_proxy_entry()` | Raise when get_db_connection is entered from outside the graph proxies. |
| `_ensure_meta_table(conn)` | — |
| `_ensure_images_table(conn)` | — |
| `_ensure_comparisons_table(conn)` | — |
| `init_database()` | Initialize database with all required tables. |
| `_set_meta_value(key, value)` | — |
| `vacuum_database()` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `MU0` | `25.0` |
| `SIGMA0` | `MU0 / 3.0` |


## `infrastructure\persistence\deduplicate_scored.py`

> Deduplicate scored images by comparing companion image MD5 across tier folders.

### Module-level functions

| Name | Description |
|---|---|
| `_md5(path)` | — |
| `_merge_comparison_histories(keeper, discard, filename)` | — |
| `deduplicate_scored(root=None, limit=0)` | — |
| `main()` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `JsonDict` | `dict[str, Any]` |
| `EntryTriple` | `tuple[Path, Path, JsonDict]` |
| `_EXAMPLE_COUNT` | `3` |


## `infrastructure\persistence\folder_organizer.py`

> Folder organizer - maintain score folder structure.

### Module-level functions

| Name | Description |
|---|---|
| `ensure_tier_structure()` | Ensure score folders exist (scored_0.0 through scored_1.0). |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |


## `infrastructure\persistence\images_repository.py`

> Images table operations.

### Module-level functions

| Name | Description |
|---|---|
| `get_all_images()` | — |
| `get_image(filename)` | — |
| `add_image(filename, score=0.5, comparison_count=0, prompt_tags=None, rating_mu=25.0, rating_sigma=25.0 / 3.0)` | — |
| `update_image_rating_state(filename, score, rating_mu, rating_sigma, comparison_count, touch_timestamp=True, last_compared_at=None)` | — |
| `update_image_tags(filename, prompt_tags)` | — |
| `get_image_count()` | — |
| `clear_all_images()` | — |
| `reset_all_image_ratings(score=0.5)` | — |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |

### Class `SQLiteImagesRepository`

> Injected implementation of the ImageRepository port.

| Name | Description |
|---|---|
| `get_image(filename)` | — |
| `get_all_images()` | — |
| `get_image_count()` | — |
| `add_image(filename, score, comparison_count, prompt_tags, rating_mu, rating_sigma)` | — |
| `update_image_rating_state(filename, score, rating_mu, rating_sigma, comparison_count, touch_timestamp=True)` | — |
| `update_image_tags(filename, prompt_tags)` | — |
| `clear_all_images()` | — |
| `reset_all_image_ratings(score)` | — |


## `infrastructure\persistence\path_handler.py`

> Path handler - compute tier structure from scores and sync companion JSON.

### Module-level functions

| Name | Description |
|---|---|
| `prewarm_folder_cache(ranked_root)` | Eagerly populate tier folder cache for all scored_X.X directories. |
| `clear_folder_cache()` | — |
| `get_ranked_root()` | — |
| `compute_path_from_filename(filename, score)` | — |
| `find_image_path(filename)` | — |
| `_build_history_for_filename(filename, all_comparisons=None, filename_to_comparisons=None, filename_to_image_data=None)` | — |
| `_move_image_and_json(current_image, current_json, score)` | — |
| `sync_image_metadata_to_json(filename, score, rating_mu, rating_sigma, comparison_count, all_comparisons=None, filename_to_path=None, filename_to_comparisons=None, filename_to_image_data=None, filename_to_entry=None)` | Rewrite one JSON companion file from DB-backed state. |

### Module-level constants

| Symbol | Description |
|---|---|
| `logger` | `get_logger(__name__)` |
| `_folder_listdir_cache` | `{}` |

## Documented paths not yet on disk (from README / REORGANIZATION_PLAN)

The README and REORGANIZATION_PLAN describe the following paths that do
not exist on disk yet. They are tracked here so the index and the docs
stay in sync.

| Path | Documented intent |
|---|---|
| `tests/test_architecture.py` | README “Dependency Violation Test”. AST-based layer-import scan; not created while test authoring is on hold |

The v4 rename targets (`build`/`analyze`/`database`/`training` endpoints and
frontends, `endpoints/files.py`) previously listed here are on disk now and
indexed above.
