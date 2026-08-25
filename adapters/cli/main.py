"""CLI entry point - argparse dispatch to the section command modules.

The only module allowed lazy inline imports (parser-dispatch pattern).
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Protocol

from ...core.observability.logger import (
    get_logger,
    ModuleLogger,
    configure_package_logging,
)

logger: ModuleLogger = get_logger(__name__)


class _SubParsers(Protocol):
    def add_parser(self, name: str, **kwargs: Any) -> argparse.ArgumentParser: ...


def _add_server_parser(
    subparsers: _SubParsers,
) -> argparse.ArgumentParser:
    server_parser: argparse.ArgumentParser = subparsers.add_parser(
        "server", help="Start the ranking server"
    )
    server_parser.add_argument("--host", default="0.0.0.0")
    server_parser.add_argument("--port", type=int, default=5001)
    server_parser.add_argument("--debug", action="store_true")

    return server_parser


def _add_training_parser(
    subparsers: _SubParsers,
) -> argparse.ArgumentParser:
    training_parser: argparse.ArgumentParser = subparsers.add_parser(
        "training", help="Model training"
    )
    training_sub: _SubParsers = training_parser.add_subparsers(dest="training_command")

    train: argparse.ArgumentParser = training_sub.add_parser(
        "train-model", help="Train model from vectors/scores"
    )
    train.add_argument("--steps", type=int, default=100)

    hpo: argparse.ArgumentParser = training_sub.add_parser(
        "hpo", help="Hyperparameter optimization"
    )
    hpo.add_argument(
        "--cycles", type=int, default=None, help="Number of HPO cycles (generations)"
    )
    hpo.add_argument(
        "--optimization-steps",
        type=int,
        default=None,
        help="HPO optimization steps per cycle (not model training steps)",
    )
    hpo.add_argument(
        "--max-combos",
        type=int,
        default=None,
        help="Max config combinations evaluated per step",
    )

    return training_parser


def _add_build_parser(
    subparsers: _SubParsers,
) -> argparse.ArgumentParser:
    build_parser: argparse.ArgumentParser = subparsers.add_parser(
        "build", help="Data preparation pipeline"
    )
    build_sub: _SubParsers = build_parser.add_subparsers(dest="build_command")

    split: argparse.ArgumentParser = build_sub.add_parser(
        "split-vectors", help="Build split vector files"
    )
    split.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N new files (0 = no limit)",
    )
    split.add_argument(
        "--batch",
        action="store_true",
        help="Loop with --limit until no new files remain",
    )

    build_sub.add_parser("full-vectors", help="Build full vectors + text data")

    build_sub.add_parser("scores", help="Build scores + comparisons")

    all_parser: argparse.ArgumentParser = build_sub.add_parser(
        "all", help="Run full pipeline (splits -> full vectors -> scores)"
    )
    all_parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N new files per step (0 = no limit)",
    )
    all_parser.add_argument(
        "--batch",
        action="store_true",
        help="Loop with --limit until no new files remain",
    )

    return build_parser


def _add_database_parser(
    subparsers: _SubParsers,
) -> argparse.ArgumentParser:
    database_parser: argparse.ArgumentParser = subparsers.add_parser(
        "database", help="Database maintenance"
    )
    database_sub: _SubParsers = database_parser.add_subparsers(dest="database_command")

    cleanup: argparse.ArgumentParser = database_sub.add_parser(
        "cleanup", help="Clean stale comparisons and VACUUM the database"
    )
    cleanup.add_argument("--limit", type=int, default=0)

    database_sub.add_parser(
        "rebuild",
        help="Deduplicate files, clean orphaned files, clear database, then repopulate from ranked files",
    )

    database_sub.add_parser(
        "recalculate", help="Recalculate scores/replay from existing data"
    )

    return database_parser


def _add_files_parser(
    subparsers: _SubParsers,
) -> tuple[
    argparse.ArgumentParser,
    argparse.ArgumentParser,
    argparse.ArgumentParser,
]:
    files_parser: argparse.ArgumentParser = subparsers.add_parser(
        "files", help="File management"
    )
    files_sub: _SubParsers = files_parser.add_subparsers(dest="files_command")

    remove: argparse.ArgumentParser = files_sub.add_parser(
        "remove",
        help="Remove specific categories of generated files (vectors, generated models, vector maps, or downloaded models)",
    )
    remove_sub: _SubParsers = remove.add_subparsers(dest="remove_command")
    remove_sub.add_parser(
        "vectors", help="Remove full vector files and all splits except image/"
    )
    remove_sub.add_parser("generated-models", help="Remove output/models/")
    remove_sub.add_parser(
        "vector-maps", help="Remove output/maps/ and vector map splits"
    )
    remove_sub.add_parser(
        "downloaded-models", help="Remove downloaded_models/ (mediapipe)"
    )

    download: argparse.ArgumentParser = files_sub.add_parser(
        "download", help="Download models from prepare config"
    )
    download_sub: _SubParsers = download.add_subparsers(dest="download_command")
    download_sub.add_parser(
        "models",
        help="Download all models in prepare config (HF/timm/torch.hub + mediapipe)",
    )

    files_sub.add_parser(
        "cleanup",
        help="Deduplicate scored entries, then move remaining orphaned files to root",
    )

    return files_parser, remove, download


def _add_analyze_parser(
    subparsers: _SubParsers,
) -> argparse.ArgumentParser:
    analyze_parser: argparse.ArgumentParser = subparsers.add_parser(
        "analyze", help="Analysis queries"
    )
    analyze_sub: _SubParsers = analyze_parser.add_subparsers(dest="analyze_command")

    analyze_sub.add_parser(
        "parameters", help="Run parameter analysis -> generates report"
    )
    analyze_sub.add_parser(
        "matrix", help="Build co-occurrence matrix -> matrix_analysis.json"
    )
    analyze_sub.add_parser(
        "stats", help="Print image/scores/comparisons summary to stdout"
    )

    return analyze_parser


def main() -> int:
    fmt: str = "[%(levelname)s] [%(name)s] [%(funcName)s] [%(asctime)s] \n%(message)s"

    configure_package_logging(
        logging.DEBUG, fmt=fmt, trim_level_len=1, trim_module_len=10, trim_func_len=None
    )
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="comfyui-scorer",
        description="Image scoring CLI for ComfyUI",
    )

    subparsers: _SubParsers = parser.add_subparsers(dest="command")

    _add_server_parser(subparsers)
    training_parser: argparse.ArgumentParser = _add_training_parser(subparsers)
    build_parser: argparse.ArgumentParser = _add_build_parser(subparsers)
    database_parser: argparse.ArgumentParser = _add_database_parser(subparsers)
    files_parser: argparse.ArgumentParser
    files_remove_parser: argparse.ArgumentParser
    files_download_parser: argparse.ArgumentParser
    files_parser, files_remove_parser, files_download_parser = _add_files_parser(
        subparsers
    )
    analyze_parser: argparse.ArgumentParser = _add_analyze_parser(subparsers)

    args: argparse.Namespace = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "server":
        from .commands.server import run_server

        return run_server(host=args.host, port=args.port, debug=args.debug)

    from .deps import CLIDeps, build_cli_deps

    deps: CLIDeps = build_cli_deps()

    if args.command == "training":
        from .commands.training import train_model, run_hpo

        if args.training_command == "train-model":
            return train_model(deps=deps)
        elif args.training_command == "hpo":
            return run_hpo(
                deps=deps,
                cycles=args.cycles,
                optimization_steps=args.optimization_steps,
                max_combos=args.max_combos,
            )
        else:
            training_parser.print_help()
            return 1

    elif args.command == "build":
        from .commands.vectors import (
            run_split_vectors,
            run_full_vectors,
            run_scores,
            run_all,
        )

        if args.build_command == "split-vectors":
            return run_split_vectors(limit=args.limit, batch=args.batch, deps=deps)
        elif args.build_command == "full-vectors":
            return run_full_vectors(deps=deps)
        elif args.build_command == "scores":
            return run_scores(deps=deps)
        elif args.build_command == "all":
            return run_all(limit=args.limit, batch=args.batch, deps=deps)
        else:
            build_parser.print_help()
            return 1

    elif args.command == "database":
        from .commands.database import cleanup, rebuild, recalculate

        if args.database_command == "cleanup":
            return cleanup(deps=deps)
        elif args.database_command == "rebuild":
            return rebuild(deps=deps)
        elif args.database_command == "recalculate":
            return recalculate(deps=deps)
        else:
            database_parser.print_help()
            return 1

    elif args.command == "files":
        from ...core.utilities.helpers import (
            delete_full_vectors,
            remove_models,
            remove_directory,
        )
        from ...core.filesystem.paths import maps_dir, mediapipe_models_dir, split_dir

        if args.files_command == "remove":
            if args.remove_command == "vectors":
                delete_full_vectors()
                return 0
            elif args.remove_command == "generated-models":
                remove_models()
                return 0
            elif args.remove_command == "vector-maps":
                remove_directory(Path(maps_dir))
                remove_directory(Path(split_dir) / "map")
                return 0
            elif args.remove_command == "downloaded-models":
                remove_directory(Path(mediapipe_models_dir))
                return 0
            else:
                files_remove_parser.print_help()
                return 1
        elif args.files_command == "download":
            if args.download_command == "models":
                deps.set_hub_offline(False)
                # #37a: restore the process's offline default even when a download fails
                try:
                    deps.download_configured_models()
                    deps.download_mediapipe_models()
                finally:
                    deps.set_hub_offline(True)
                return 0
            else:
                files_download_parser.print_help()
                return 1
        elif args.files_command == "cleanup":
            dedup_count: int = deps.deduplicate_scored(
                root=None,
            )
            logger.info("Duplicates removed: %s", dedup_count)
            orphan_count: int = deps.cleanup_orphans(root=None)
            logger.info("Orphans cleaned: %s", orphan_count)
            return 0
        else:
            files_parser.print_help()
            return 1

    elif args.command == "analyze":
        if args.analyze_command == "parameters":
            from ...application.analysis.run_parameter_analysis import (
                run_parameter_analysis,
            )

            return run_parameter_analysis()
        elif args.analyze_command == "matrix":
            from ...application.analysis.run_matrix_analysis import run_matrix_analysis

            return run_matrix_analysis()
        elif args.analyze_command == "stats":
            from ...application.analysis.run_stats import run_stats

            return run_stats(graph=deps.graph)
        else:
            analyze_parser.print_help()
            return 1
    return 0


if __name__ == "__main__":

    sys.exit(main())
