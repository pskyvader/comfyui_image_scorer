import argparse
import sys
from typing import Optional


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="comfyui-scorer",
        description="Image scoring CLI for ComfyUI",
    )
    subparsers = parser.add_subparsers(dest="command")

    server_parser = subparsers.add_parser("server", help="Start the ranking server")
    server_parser.add_argument("--host", default="127.0.0.1")
    server_parser.add_argument("--port", type=int, default=5000)

    training_parser = subparsers.add_parser("training", help="Run training pipeline")
    training_parser.add_argument("--steps", type=int, default=100)

    vectors_parser = subparsers.add_parser("vectors", help="Manage vectors")
    vectors_parser.add_argument("--rebuild", action="store_true")

    database_parser = subparsers.add_parser("database", help="Database operations")
    database_parser.add_argument("--cleanup", action="store_true")
    database_parser.add_argument("--deduplicate", action="store_true")

    args = parser.parse_args()

    if args.command == "server":
        return _run_server(args.host, args.port)
    elif args.command == "training":
        return _run_training(args.steps)
    elif args.command == "vectors":
        return _run_vectors(args.rebuild)
    elif args.command == "database":
        return _run_database(args.cleanup, args.deduplicate)
    else:
        parser.print_help()
        return 0


def _run_server(host: str, port: int) -> int:
    print(f"Starting server on {host}:{port}")
    return 0


def _run_training(steps: int) -> int:
    print(f"Running training for {steps} steps")
    return 0


def _run_vectors(rebuild: bool) -> int:
    print(f"Managing vectors (rebuild={rebuild})")
    return 0


def _run_database(cleanup: bool, deduplicate: bool) -> int:
    print(f"Database operations (cleanup={cleanup}, deduplicate={deduplicate})")
    return 0