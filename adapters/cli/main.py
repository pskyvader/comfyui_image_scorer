import argparse
import os
import sys

from ...core.observability.logger import get_logger

logger = get_logger(__name__)


def _add_build_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    build_parser = subparsers.add_parser("build", help="Data preparation pipeline")
    build_sub = build_parser.add_subparsers(dest="build_command")

    split = build_sub.add_parser("split-vectors", help="Build split vector files")
    split.add_argument(
        "--limit", type=int, default=0, help="Process at most N new files (0 = no limit)"
    )
    split.add_argument(
        "--batch",
        action="store_true",
        help="Loop with --limit until no new files remain",
    )

    build_sub.add_parser("full-vectors", help="Build full vectors + text data")

    build_sub.add_parser("scores", help="Build scores + comparisons")

    all_parser = build_sub.add_parser(
        "all", help="Run full pipeline (splits -> full vectors -> scores)"
    )
    all_parser.add_argument(
        "--limit", type=int, default=0, help="Process at most N new files per step (0 = no limit)"
    )
    all_parser.add_argument(
        "--batch",
        action="store_true",
        help="Loop with --limit until no new files remain",
    )

    return build_parser


def _add_training_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    training_parser = subparsers.add_parser("training", help="Model training")
    training_sub = training_parser.add_subparsers(dest="training_command")

    train = training_sub.add_parser("train-model", help="Train model from vectors/scores")
    train.add_argument("--steps", type=int, default=100)

    hpo = training_sub.add_parser("hpo", help="Hyperparameter optimization")
    hpo.add_argument("--cycles", type=int, default=None, help="Number of HPO cycles (generations)")
    hpo.add_argument("--optimization-steps", type=int, default=None, help="HPO optimization steps per cycle (not model training steps)")
    hpo.add_argument("--max-combos", type=int, default=None, help="Max config combinations evaluated per step")

    return training_parser


def _add_database_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    database_parser = subparsers.add_parser("database", help="Database maintenance")
    database_sub = database_parser.add_subparsers(dest="database_command")

    cleanup = database_sub.add_parser("cleanup", help="Clean stale comparisons and VACUUM the database")
    cleanup.add_argument("--limit", type=int, default=0)

    database_sub.add_parser("rebuild", help="Deduplicate files, clean orphaned files, clear database, then repopulate from ranked files")

    database_sub.add_parser("recalculate", help="Recalculate scores/replay from existing data")

    return database_parser


def _add_files_parser(subparsers: argparse._SubParsersAction) -> tuple[argparse.ArgumentParser, argparse.ArgumentParser, argparse.ArgumentParser, argparse.ArgumentParser]:
    files_parser = subparsers.add_parser("files", help="File management")
    files_sub = files_parser.add_subparsers(dest="files_command")

    remove = files_sub.add_parser("remove", help="Remove specific categories of generated files (vectors, models, maps, or downloaded models)")
    remove_sub = remove.add_subparsers(dest="remove_command")
    remove_sub.add_parser("vectors", help="Remove full vector files (splits NEVER deleted)")
    remove_sub.add_parser("models", help="Remove output/models/")
    remove_sub.add_parser("maps", help="Remove output/maps/")
    remove_sub.add_parser("downloaded-models", help="Remove downloaded_models/ (mediapipe)")

    download = files_sub.add_parser("download", help="Download models from prepare config")
    download_sub = download.add_subparsers(dest="download_command")
    download_sub.add_parser("models", help="Download all models in prepare config (HF/timm/torch.hub + mediapipe)")

    cleanup_parser = files_sub.add_parser("cleanup", help="Deduplicate scored entries, then move remaining orphaned files to root")
    cleanup_parser.add_argument("--limit", type=int, default=0)
    cleanup_parser.add_argument("--dry-run", action="store_true")

    return files_parser, remove, download, cleanup_parser


def _add_analyze_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    analyze_parser = subparsers.add_parser("analyze", help="Analysis queries")
    analyze_sub = analyze_parser.add_subparsers(dest="analyze_command")

    analyze_sub.add_parser("parameters", help="Run parameter analysis -> generates report")
    analyze_sub.add_parser("matrix", help="Build co-occurrence matrix -> matrix_analysis.json")
    analyze_sub.add_parser("stats", help="Print image/scores/comparisons summary to stdout")

    return analyze_parser


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="comfyui-scorer",
        description="Image scoring CLI for ComfyUI",
    )
    subparsers = parser.add_subparsers(dest="command")

    server_parser = subparsers.add_parser("server", help="Start the ranking server")
    server_parser.add_argument("--host", default="0.0.0.0")
    server_parser.add_argument("--port", type=int, default=5001)
    server_parser.add_argument("--debug", action="store_true")

    training_parser = _add_training_parser(subparsers)
    build_parser = _add_build_parser(subparsers)
    database_parser = _add_database_parser(subparsers)
    files_parser, files_remove_parser, files_download_parser, files_cleanup_parser = _add_files_parser(subparsers)
    analyze_parser = _add_analyze_parser(subparsers)

    args = parser.parse_args()

    if args.command == "server":
        from .commands.server import run_server
        return run_server(host=args.host, port=args.port, debug=args.debug)

    elif args.command == "training":
        from .commands.training import train_model, run_hpo
        if args.training_command == "train-model":
            return train_model(steps=args.steps)
        elif args.training_command == "hpo":
            return run_hpo(
                cycles=args.cycles,
                optimization_steps=args.optimization_steps,
                max_combos=args.max_combos,
            )
        else:
            training_parser.print_help()
            return 1

    elif args.command == "build":
        from .commands.vectors import run_split_vectors, run_full_vectors, run_scores, run_all
        if args.build_command == "split-vectors":
            return run_split_vectors(limit=args.limit, batch=args.batch)
        elif args.build_command == "full-vectors":
            return run_full_vectors()
        elif args.build_command == "scores":
            return run_scores()
        elif args.build_command == "all":
            return run_all(limit=args.limit, batch=args.batch)
        else:
            build_parser.print_help()
            return 1

    elif args.command == "database":
        from .commands.database import cleanup, rebuild, recalculate
        if args.database_command == "cleanup":
            return cleanup(limit=args.limit)
        elif args.database_command == "rebuild":
            return rebuild()
        elif args.database_command == "recalculate":
            return recalculate()
        else:
            database_parser.print_help()
            return 1

    elif args.command == "files":
        from ...core.utilities.helpers import (
            delete_full_vectors, remove_models, remove_directory,
        )
        from ...core.filesystem.paths import maps_dir, mediapipe_models_dir
        from pathlib import Path

        if args.files_command == "remove":
            if args.remove_command == "vectors":
                delete_full_vectors()
                return 0
            elif args.remove_command == "models":
                remove_models()
                return 0
            elif args.remove_command == "maps":
                remove_directory(Path(maps_dir))
                return 0
            elif args.remove_command == "downloaded-models":
                remove_directory(Path(mediapipe_models_dir))
                return 0
            else:
                files_remove_parser.print_help()
                return 1
        elif args.files_command == "download":
            if args.download_command == "models":
                os.environ["HF_HUB_OFFLINE"] = "0"
                from ...infrastructure.ml_models.model_loader import download_configured_models
                from ...infrastructure.external_services.mediapipe_models import download_mediapipe_models
                download_configured_models()
                download_mediapipe_models()
                return 0
            else:
                files_download_parser.print_help()
                return 1
        elif args.files_command == "cleanup":
            from ...infrastructure.persistence.cleanup_orphans import cleanup_orphans
            from ...infrastructure.persistence.deduplicate_scored import deduplicate_scored
            dedup_count = deduplicate_scored(
                root=None, dry_run=args.dry_run, limit=args.limit,
            )
            logger.info("Duplicates removed: %s", dedup_count)
            orphan_count = cleanup_orphans(
                root=None, dry_run=args.dry_run, delete_enabled=not args.dry_run,
            )
            logger.info("Orphans cleaned: %s", orphan_count)
            return 0
        else:
            files_parser.print_help()
            return 1

    elif args.command == "analyze":
        if args.analyze_command == "parameters":
            from ...application.analysis.run_parameter_analysis import run_parameter_analysis
            return run_parameter_analysis()
        elif args.analyze_command == "matrix":
            from ...application.analysis.run_matrix_analysis import run_matrix_analysis
            return run_matrix_analysis()
        elif args.analyze_command == "stats":
            from ...application.analysis.run_stats import run_stats
            return run_stats()
        else:
            analyze_parser.print_help()
            return 1

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
