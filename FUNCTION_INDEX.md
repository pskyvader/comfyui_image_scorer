# Function Index — comfyui_image_scorer

All functions, methods, and classes grouped by file (paths relative to `comfyui_image_scorer`).

---

## `__init__.py`

| Name | Description |
|---|---|
| `__getattr__(name)` | Lazy-loads `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` from `adapters.comfyui` |

---

## `scorer.py`

| Name | Description |
|---|---|
| *(module-level script)* | Inserts parent dir into `sys.path`, imports `main` from `adapters.cli.main`, exits with its return code |

---

## `core/configuration/settings.py`

### Module-level functions

| Name | Description |
|---|---|
| `_get_config_file(path)` | Resolves a relative path against `PROJECT_ROOT`; returns absolute `Path` |
| `_load_raw_config(path)` | Loads and returns a JSON config dict from disk (empty dict on failure) |
| `_save_raw_config(data, path)` | Writes a config dict to a JSON file on disk, creating parent dirs |
| `ensure_dir(path)` | Creates directories with `os.makedirs(..., exist_ok=True)` |

### Class `AutoSaveDict` (MutableMapping)

| Name | Description |
|---|---|
| `__init__(self, data, save_callback)` | Stores the underlying data dict and save callback |
| `get(self, key, default=_sentinel)` | Gets a value; raises `ValueError` if default is provided (banned) |
| `__getitem__(self, key)` | Gets item by key, wrapping nested dicts in another `AutoSaveDict` |
| `__setitem__(self, key, value)` | Sets item and triggers save callback |
| `__delitem__(self, key)` | Deletes item and triggers save callback |
| `__iter__(self)` | Yields keys from underlying data |
| `__len__(self)` | Returns number of keys |
| `copy(self)` | Returns a shallow copy of the underlying dict |
| `__repr__(self)` | Returns repr of underlying dict |

### Class `Config` (MutableMapping)

| Name | Description |
|---|---|
| `__init__(self, config_file=CONFIG_FILE)` | Initialises with a root config path, empty caches |
| `get(self, key, default=_sentinel)` | Gets a value; raises `ValueError` if default is provided (banned) |
| `_get_root(self)` | Lazy-loads and caches the root config data from disk |
| `_save_root(self)` | Writes root config back to disk if loaded |
| `_get_sub(self, section)` | Loads and caches a sub-config section from its file path |
| `_save_sub(self, section)` | Writes a sub-config section back to its file |
| `__getitem__(self, key)` | Looks up key in subconfigs (wraps in `AutoSaveDict`), then root, then deep subconfig keys |
| `__setitem__(self, key, value)` | Sets value in the appropriate config section (subconfig or root) |
| `__delitem__(self, key)` | Deletes key from the appropriate section |
| `__iter__(self)` | Iterates over all keys from root, subconfig section names, and subconfig data |
| `__len__(self)` | Returns total number of unique keys |
| `clear(self)` | Clears all caches so next access re-reads from disk |

---

## `core/filesystem/paths.py`

*(No functions/classes; only module-level path constants)*

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
| `mediapipe_models_dir` | Path to `downloaded_models/` |
| `training_model` | Path to `output/models/model.npz` |
| `vectors_data` | Path to `output/models/vectors.npz` |
| `scores_data` | Path to `output/models/scores.npz` |
| `comparisons_data` | Path to `output/models/comparisons.npz` |
| `feature_rule` | Path to `output/models/feature_rule.npz` |
| `comparison_rule` | Path to `output/models/comparison_rule.npz` |
| `interaction_data` | Path to `output/models/interaction_data.npz` |

---

## `core/observability/logger.py`

### Module-level functions

| Name | Description |
|---|---|
| `_custom_find_caller(self, stack_info, stacklevel)` | Custom `findCaller` that skips `logger.py` frames to report the true caller |
| `_is_progress_line(line)` | Returns `True` if line contains progress indicators (`%`, `|`, `img/s`, etc.) |
| `set_log_filter_hook(fn)` | Installs a global hook called for every output line |
| `get_logger(module_name=None)` | Returns root logger if `None`, else a `ModuleLogger` |
| `configure_package_logging(level, fmt, ...)` | Sets up console handler with `CustomFormatter`, configures package-level logger |
| `log_message(module_name, level_name, message, start_timer, task_id)` | Convenience wrapper that delegates to `SharedLogger.log(...)` |

### Class `_TaskOutput`

| Name | Description |
|---|---|
| `context(task_id)` | Context manager that sets the current thread's task_id |
| `current_task_id()` | Returns current thread's task_id or `None` |
| `register_buffer(task_id, lines)` | Associates a list buffer with a task_id |
| `unregister_buffer(task_id)` | Removes the buffer for a task_id |
| `has_buffer(task_id)` | Checks whether a buffer exists for a task_id |
| `write(task_id, line, *, is_progress, module_name)` | Writes line to task buffer, applies filter hook, trims to `MAX_LINES`, optionally broadcasts via SSE |

### Class `CaptureStream` (io.TextIOBase)

| Name | Description |
|---|---|
| `__init__(self, lines, original_stream, *, task_id)` | Stores lines buffer, original stream, optional task_id |
| `write(self, s)` | Writes to original stream, accumulates buffer, splits on newlines |
| `_process_line(self, line)` | Routes completed line to `_TaskOutput` or local buffer |
| `flush(self)` | Flushes the original stream |
| `_flush_remaining(self)` | Flushes any remaining buffered content |

### Class `SSELogBroadcaster`

| Name | Description |
|---|---|
| `_ensure_dispatch()` | Starts the background dispatch thread once |
| `_dispatch_loop()` | Background loop that batches up to 50 lines into subscriber queues |
| `subscribe()` | Registers a new SSE subscriber, returns `(sub_id, Queue)` |
| `unsubscribe(sub_id)` | Removes a subscriber by ID |
| `broadcast(line)` | Queues a log line for dispatch to all subscribers |

### Class `_DynamicModuleFilter` (logging.Filter)

| Name | Description |
|---|---|
| `filter(self, record)` | Returns `SharedLogger.should_emit(record.name)` |

### Class `TaskLogHandler` (logging.Handler)

| Name | Description |
|---|---|
| `__init__(self, lines, owner_thread_id)` | Stores buffer and the owning thread's ID |
| `emit(self, record)` | Formats and writes log records that bypass `SharedLogger` into task buffer/SSE stream |

### Class `ModuleLogger`

| Name | Description |
|---|---|
| `__init__(self, module_name)` | Stores the module name |
| `_underlying` (property) | Returns the real `logging.Logger` for this module |
| `level` (property) | Gets/sets underlying logger level |
| `setLevel(self, level)` | Sets underlying logger level |
| `addHandler(self, hdlr)` | Adds a handler to the underlying logger |
| `removeHandler(self, hdlr)` | Removes a handler from the underlying logger |
| `log(self, level_name, message, *args, start_timer)` | Interpolates args and delegates to `SharedLogger.log(...)` |
| `debug(self, message, *args, start_timer)` | Logs at DEBUG level |
| `info(self, message, *args, start_timer)` | Logs at INFO level |
| `warning(self, message, *args, start_timer)` | Logs at WARNING level |
| `error(self, message, *args, start_timer)` | Logs at ERROR level |
| `exception(self, message, *args, start_timer)` | Logs at ERROR level (for exceptions) |
| `critical(self, message, *args, start_timer)` | Logs at CRITICAL level |

### Class `SharedLogger`

| Name | Description |
|---|---|
| `install_root_filter()` | Adds the dynamic module filter to the root logger |
| `set_name_filters(exact_names, prefixes)` | Sets allowed exact names and prefix-based module filters |
| `clear_name_filters()` | Clears all module name filters |
| `set_frontend_enabled(enabled)` | Enables/disables frontend (task buffer + SSE) logging |
| `set_frontend_level(level_name)` | Sets the minimum level for frontend output |
| `should_emit(module_name)` | Checks whether a module name passes current name filters |
| `get_logger(module_name)` | Installs root filter and returns a `ModuleLogger` |
| `register_task_buffer(task_id, lines)` | Delegates to `_TaskOutput.register_buffer(...)` |
| `unregister_task_buffer(task_id)` | Delegates to `_TaskOutput.unregister_buffer(...)` |
| `task_context(task_id)` | Context manager delegating to `_TaskOutput.context(...)` |
| `current_task_id()` | Delegates to `_TaskOutput.current_task_id()` |
| `format_message(message, start_timer)` | Appends caller name and elapsed time to message |
| `format_task_line(module_name, level_name, message)` | Formats a task output line as `"LEVEL MODULE - message"` |
| `log(module_name, level_name, message, start_timer, task_id)` | Main log method: filters, formats, logs via Python logger, writes to frontend |
| `_normalize_level(level_name)` | Converts a level name string to `logging` int constant |

### Class `CustomFormatter` (logging.Formatter)

| Name | Description |
|---|---|
| `__init__(self, fmt, datefmt, trim_level_len, trim_module_len, trim_func_len, trim_msg_len)` | Stores trimming parameters |
| `format(self, record)` | Trims levelname, name, funcName, message; formats; restores originals |

---

## `core/io/serialization.py`

| Name | Description |
|---|---|
| `load_single_jsonl(filename, skip_invalid)` | Yields parsed JSON objects from each non-empty line of a JSONL file |
| `write_single_jsonl(filename, data, mode)` | Writes a list of items to a JSONL file with a tqdm progress bar |
| `parallel_batch(fn, items)` | Executes `fn(*item)` for each item sequentially in a batch |
| `parallel_for(fn, items, *, max_workers, batch_size, desc, unit, on_progress)` | Executes `fn(*item)` across a `ThreadPoolExecutor` with optional batching and progress bar |
| `discover_files(root)` | Walks a directory yielding `(image_path, metadata_path)` for images with a companion `.json` file |
| `collect_single_file(file, processed_files, root)` | Processes one image/metadata pair, returning `(img_path, metadata, timestamp, file_id)` or `None` |
| `collect_valid_files(files, processed_files, root, limit, max_workers, scored_only)` | Collects valid image/metadata pairs from discovered files using a thread pool |
| `_recursive_parse_json(obj, path)` | Recursively parses JSON-encoded strings within a deserialized JSON structure |
| `load_json(path, expect)` | Loads a JSON file, optionally validates its type, returns `(data, err)` |
| `atomic_write_json(path, data, *, indent)` | Atomically writes JSON to a file via a temp file and `os.replace` |
| `load_single_entry_mapping(path)` | Loads a JSON dict with exactly one key, returns `(payload, key, err)` |

---

## `domain/database/schema.py`

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

---

## `domain/database/comparisons_table.py`

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

## `domain/database/ports/repository_ports.py`

### Protocol `ImageRepository`

| Name | Description |
|---|---|
| `get_image(self, filename)` | Returns image data dict or `None` |
| `get_all_images(self)` | Returns list of all image data dicts |
| `add_image(self, filename, score, comparison_count, prompt_tags, rating_mu, rating_sigma)` | Inserts an image record |
| `update_image_rating_state(self, filename, score, rating_mu, rating_sigma, comparison_count)` | Updates rating fields for an image |

### Protocol `ComparisonRepository`

| Name | Description |
|---|---|
| `add_comparison(self, filename_a, filename_b, winner, impact_factor, phase)` | Inserts a comparison record |
| `get_all_comparisons(self)` | Returns all comparison records |
| `get_total_comparisons(self)` | Returns total comparison count |
| `comparison_exists_for_pair(self, filename_a, filename_b)` | Checks existence of a comparison |

### Protocol `PathResolver`

| Name | Description |
|---|---|
| `sync_image_metadata_to_json(self, filename)` | Syncs image metadata to a JSON sidecar file |

---

## `domain/graph/node_proxy.py`

### Class `NodeProxy`

| Name | Description |
|---|---|
| `__init__(self, chain, node_id, image_data)` | Stores chain manager, node ID, optional image data |
| `id` (property) | Returns the node ID string |
| `filename` (property) | Returns the node ID (aliased as filename) |
| `score` (property) | Returns image score, defaulting to `0.5` |
| `mu_skill` (property) | Returns rating mu, defaulting to `25.0` |
| `sigma_uncertainty` (property) | Returns rating sigma, defaulting to `25.0/3.0` |
| `comparison_count` (property) | Returns comparison count, defaulting to `0` |
| `chain_count` (property) | Returns number of chains this node appears in |
| `main_chain_in_chains` (property) | Returns whether the node's main chain ID is in its chain list |
| `prompt_tags` (property) | Returns prompt tags string or `None` |
| `last_compared_at` (property) | Returns last comparison timestamp string or `None` |
| `is_top(self)` | Delegates to chain manager to check if node is a top node |
| `is_bottom(self)` | Delegates to chain manager to check if node is a bottom node |
| `get_links(self, better_than, worse_than)` | Returns unique `NodeProxy` objects linked to this node, filtered by direction |
| `get_chain(self, only_main)` | Returns `ChainProxy` objects for the node's main chain or all chains |
| `get_position_in_chain(self)` | Returns the node's index within its main chain |
| `get_component(self)` | Returns `ComponentProxy` for the node's connected component |
| `__repr__` | Returns `NodeProxy(<node_id>)` |

---

## `domain/graph/chain_proxy.py`

### Class `ChainProxy`

| Name | Description |
|---|---|
| `__init__(self, chain, chain_id, node_list)` | Stores chain manager, chain ID, node list |
| `id` (property) | Returns chain ID integer |
| `nodes` (property) | Returns list of `NodeProxy` for all nodes in this chain |
| `length` (property) | Returns number of nodes in the chain |
| `is_main` (property) | Returns `True` if any node has this chain as its main chain |
| `first` (property) | Returns first `NodeProxy` in chain, or `None` |
| `last` (property) | Returns last `NodeProxy` in chain, or `None` |
| `get_nodes(self, only_top, only_bottom)` | Returns filtered list of `NodeProxy` by top/bottom status |
| `node_position(self, node_id)` | Returns index of a node ID within the chain |
| `get_component(self)` | Returns `ComponentProxy` for the first node's component |
| `__repr__` | Returns `ChainProxy(id=..., length=...)` |

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
| `strongconnect(v)` | (nested inside `tarjan_scc`) Recursive DFS helper that assigns indices/lowlinks and emits SCCs |

### Class `ChainManager`

| Name | Description |
|---|---|
| `__init__(self)` | Initialises all internal graph data structures (empty) |
| `get_all_filenames(self)` | Returns set of all filenames in the graph |
| `get_top_nodes(self)` | Returns list of top (no-predecessor) nodes |
| `get_bottom_nodes(self)` | Returns list of bottom (no-successor) nodes |
| `get_better_than(self, node_id)` | Returns list of nodes better than (predecessors of) the given node |
| `get_worse_than(self, node_id)` | Returns list of nodes worse than (successors of) the given node |
| `is_top(self, node_id)` | Checks if a node is a top node |
| `is_bottom(self, node_id)` | Checks if a node is a bottom node |
| `get_component_id(self, node_id)` | Returns the connected component ID for a node |
| `get_component_members(self, comp_id)` | Returns filenames in a component by component ID |
| `get_component_count(self)` | Returns total number of connected components |
| `get_built_at(self)` | Returns the timestamp the graph was built |
| `set_built_at(self, dt)` | Stores the build timestamp |
| `get_db_comparison_count(self)` | Returns the DB comparison count snapshot |
| `set_db_comparison_count(self, count)` | Stores the DB comparison count snapshot |
| `build(self, comparisons, all_filenames)` | Full rebuild: resets adjacency, builds from comparisons, identifies tops/bottoms, builds components and chains |
| `_reset_adjacency(self)` | Clears all directed/undirected adjacency structures |
| `_build_from_comparisons(self, comparisons)` | Iterates comparisons and adds edges |
| `apply_comparison(self, winner, loser)` | Incremental update: adds a single comparison edge, updates top/bottom, merges components |
| `_remove_from_bottom_if_not_anymore(self, winner)` | Removes winner from bottom if it now has outgoing edges |
| `_remove_from_top_if_not_anymore(self, loser)` | Removes loser from top if it now has incoming edges |
| `_add_to_bottom_if_needed(self, loser)` | Adds loser to bottom if it has no outgoing edges |
| `_add_to_top_if_needed(self, winner)` | Adds winner to top if it has no incoming edges |
| `_update_top_bottom_for_edge(self, winner, loser)` | Updates top/bottom sets after adding a new edge |
| `_component_of(self, node)` | Returns component ID for a node |
| `_both_have_components_and_different(self, cw, cl)` | Returns True if both nodes have components and they differ |
| `_neither_has_component(self, cw, cl)` | Returns True if neither node has a component |
| `_winner_lacks_component(self, cw, cl)` | Returns True if winner has no component but loser does |
| `_loser_lacks_component(self, cw, cl)` | Returns True if loser has no component but winner does |
| `_create_new_component(self, winner, loser)` | Creates a new component containing both winner and loser |
| `_add_winner_to_loser_component(self, winner, cl)` | Adds winner to loser's existing component |
| `_add_loser_to_winner_component(self, loser, cw)` | Adds loser to winner's existing component |
| `_merge_node_components(self, winner, loser)` | Merges or creates components for a newly connected pair |
| `_ensure_larger_component_kept(self, keep_id, remove_id)` | Returns IDs swapped so the larger component is kept |
| `_reassign_nodes(self, remove_id, keep_id)` | Reassigns all nodes from the removed component to the kept one |
| `_absorb_removed_component(self, keep_id, remove_id)` | Merges member lists from remove_id into keep_id and deletes remove_id |
| `_merge_components(self, keep_id, remove_id)` | Merges two components, keeping the larger one |
| `_identify_top_bottom(self)` | Populates top and bottom node sets via helper functions |
| `_build_components(self)` | Populates component structures via `build_components` |
| `_dedup_path(path)` | Deduplicates a path by stopping at first repeated element |
| `_build_chains(self)` | Builds chains using forward/backward DP on SCC-condensed DAG |
| `get_chains(self)` | Returns dict of all `{chain_id: [node_list]}` pairs |
| `get_node_chains(self, node_id)` | Returns all `(chain_id, chain_list)` pairs for a node |
| `get_node_main_chain(self, node_id)` | Returns the main `(chain_id, chain_list)` for a node |
| `get_min_chain_count(self)` | Returns the number of chains |
| `_quick_reject(self, start, end)` | Quick pre-checks for reachability (missing node, different component, no edges) |
| `_bfs_search(self, start, end, max_depth)` | BFS to find if `end` is reachable from `start` up to `max_depth` |
| `_can_reach(self, start, end)` | Checks reachability using quick reject, same-chain check, then BFS |
| `_check_same_chain(self, u, v)` | Returns `(same_chain, u_before_v)` for two nodes |

---

## `domain/graph/component_proxy.py`

### Class `ComponentProxy`

| Name | Description |
|---|---|
| `__init__(self, chain, comp_id)` | Stores chain manager and component ID |
| `id` (property) | Returns component ID integer |
| `nodes` (property) | Returns list of `NodeProxy` for all nodes in the component |
| `size` (property) | Returns number of nodes in the component |
| `get_chains(self, minimal_required)` | Returns all `ChainProxy` objects whose chains intersect this component |
| `__repr__` | Returns `ComponentProxy(id=..., size=...)` |

---

## `domain/graph/crystal_graph.py`

### Class `CrystalGraph`

| Name | Description |
|---|---|
| `__init__(self, image_repo, comparison_repo)` | Creates internal `ChainManager`, empty image/comparison stores, optionally stores repos |
| `get_node_chain_length(self, filename)` | Returns length of the node's main chain (0 if none) |
| `get_main_chain_member_count(self, chain_id)` | Returns how many nodes have `chain_id` as their main chain |
| `rebuild_from_database(self, images, comparisons)` | Full rebuild: loads images/comparisons from repos or args, builds ChainManager, builds chain map |
| `apply_comparison(self, winner, loser)` | Delegates a single comparison to the ChainManager |
| `is_cache_stale(self)` | Checks whether the DB comparison count differs from the snapshot |
| `get_node(self, node_id)` | Returns `NodeProxy` for given node ID or `None` |
| `get_all_nodes(self, only_top, only_bottom)` | Returns all `NodeProxy` objects, optionally filtered by top/bottom |
| `get_chain(self, node_id, chain_id)` | Returns `ChainProxy` looked up by node ID or chain ID |
| `get_all_chains(self, min_length, sort_order)` | Returns all `(ChainProxy, [(NodeProxy, is_main)])` tuples, filtered by length and sorted |
| `get_component(self, node_id, component_id, chain_id)` | Returns `ComponentProxy` looked up by node, component, or chain ID |
| `get_all_components(self)` | Returns all `ComponentProxy` objects |
| `get_all_links(self)` | Returns all `(winner_node, loser_node)` directed edge tuples |
| `get_graph_stats(self)` | Returns a dict of graph statistics |
| `are_in_same_path(self, img1, img2)` | Checks if two images are in the same path (reachable in either direction) |
| `get_chains_map(self)` | Builds and caches chains map grouped by length |

### Class `_ImageRepo` (conditional, when not running from tests)

| Name | Description |
|---|---|
| `get_all_images()` | Static wrapper around `images_table.get_all_images` |
| `get_image(filename)` | Static wrapper around `images_table.get_image` |
| `add_image(filename, score, comparison_count, prompt_tags, rating_mu, rating_sigma)` | Static wrapper around `images_table.add_image` |
| `update_image_rating_state(filename, score, rating_mu, rating_sigma, comparison_count)` | Static wrapper around `images_table.update_image_rating_state` |

### Class `_ComparisonRepo` (conditional, when not running from tests)

| Name | Description |
|---|---|
| `get_all_comparisons()` | Static wrapper around `comparisons_table.get_all_comparisons` |
| `get_total_comparisons()` | Static wrapper around `comparisons_table.get_total_comparisons` |
| `add_comparison(filename_a, filename_b, winner, impact_factor, phase)` | Static wrapper around `comparisons_table.add_comparison` |
| `comparison_exists_for_pair(filename_a, filename_b)` | Static wrapper around `comparisons_table.comparison_exists_for_pair` |

---

## `domain/graph/tests/test_chain_manager.py`

| Name | Description |
|---|---|
| `test_bottom_nodes_are_chain_last()` | Asserts all chains start at top nodes and end at bottom nodes against real DB |
| `test_performance_on_large_chains()` | Tests ChainManager processes a large dataset in under 30 seconds |
| `test_cycles_do_not_prevent_bottom_reachability()` | Verifies cyclic paths still reach and end at the absolute bottom node |
| `test_transitive_reduction_sorting()` | Verifies `a>b, b>c, a>c` builds a single sorted chain `a>b>c` |
| `test_uncompared_nodes_are_isolated_top_bottom()` | Tests uncompared images form single-node chains acting as both top and bottom |
| `test_top_bottom_match_database_exactly()` | Asserts computed top/bottom sets exactly match DB "only-wins" and "only-losses" |
| `test_chain_snapshot_matches_known_optimal()` | Verifies exact chain output for a manually designed DAG |

---

## `domain/vectors/terms.py`

| Name | Description |
|---|---|
| `extract_weight_from_paren(text)` | Parses `(term:weight)` or `(term)` syntax, returning `(content, weight)` |
| `tokenize_by_depth(text, splitters)` | Splits text by splitters and parenthetical boundaries, respecting nesting depth |
| `clean_term(term)` | Normalizes string: lowercases, removes backslashes/pipes/punctuation/stray weight markers |
| `filter_terms(terms, connectors, splitters)` | Removes stopwords unless protected by connector/splitter sets |
| `deduplicate_terms(terms)` | Merges duplicate terms, keeping the highest weight |
| `_extract_recursive(text, current_weight, splitters)` | Recursively handles parentheses nesting and weight multiplication |
| `extract_terms(text, connectors, splitters)` | Main entry: recursively parses, cleans, filters, deduplicates prompt text into weighted terms |

### Class `ExtractionResult` (dataclass)

| Field | Description |
|---|---|
| `terms` | Final list of `(term, weight, index)` tuples |
| `raw` | Raw extracted terms before processing |
| `filtered_out` | Terms removed by stopword filtering |
| `stripped` | Terms that became empty after cleaning |
| `duplicates` | Terms removed by deduplication |

---

## `domain/vectors/tests/test_terms.py`

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

## `domain/database/ports/__init__.py`

| Name | Description |
|---|---|
| `__all__` | Exports `["ImageRepository", "ComparisonRepository", "PathResolver"]` |
| `ImageRepository` | Re-exported from `.repository_ports` (see below) |
| `ComparisonRepository` | Re-exported from `.repository_ports` (see below) |
| `PathResolver` | Re-exported from `.repository_ports` (see below) |
