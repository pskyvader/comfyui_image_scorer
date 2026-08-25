"""Architecture gates: layer-import scan + DB-proxy scan (REORGANIZATION_PLAN §4)."

The layer gate parses every module, resolves each import to its top-level
layer, and enforces the README dependency table. The DB-proxy gate flags any
module importing ``get_db_connection`` or ``infrastructure.persistence``
symbols outside the graph/persistence allowlist and the three composition
roots (blocking since the §3.12 #47 flip).
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ("core", "domain", "application", "adapters", "infrastructure")
ALLOWED = {
    "core": (),
    "domain": ("core",),
    "application": ("core", "domain"),
    "adapters": ("core", "domain", "application"),
    "infrastructure": ("core", "domain"),
}
COMPOSITION_ROOTS = {
    "adapters/server/main.py",
    "adapters/cli/deps.py",
    "adapters/comfyui/services.py",
}
DB_PROXY_ALLOWED_PREFIXES = ("domain/graph/", "infrastructure/persistence/")


def _iter_layer_files():
    for layer in LAYERS:
        for path in sorted((ROOT / layer).rglob("*.py")):
            yield path.relative_to(ROOT).as_posix(), path


def _import_targets(tree: ast.Module):
    """Yield absolute-comfort targets: ('rel', dotted.module) for relative
    imports resolved against the file's package, and ('abs', top segment) for
    plain imports."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    yield "abs", node.module
            else:
                yield "rel", node.module or "", node.level
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield "abs", alias.name


def test_no_layer_violations():
    violations = []
    for rel, path in _iter_layer_files():
        layer = rel.split("/")[0]
        allowed = ALLOWED[layer]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        pkg_parts = rel.split("/")[:-1]
        for kind, value, *rest in _import_targets(tree):
            if kind == "abs":
                segments = value.split(".")
                if segments[0] != "comfyui_image_scorer" or len(segments) < 2:
                    continue
                target = segments[1]
                if (
                    target in LAYERS
                    and target not in allowed
                    and layer != target
                    and not (target == "infrastructure" and rel in COMPOSITION_ROOTS)
                ):
                    violations.append(f"{rel}: {layer} imports {target}")
            else:
                level = rest[0]
                base = pkg_parts[: len(pkg_parts) - (level - 1)] if level > 1 else pkg_parts
                target = (base[0] if base else "")
                if target in LAYERS and target not in allowed and layer != target:
                    violations.append(f"{rel}: {layer} imports {target} (relative)")
    assert not violations, f"layer violations:\n" + "\n".join(violations)


def test_no_db_access_outside_proxies():
    violations = []
    for rel, path in _iter_layer_files():
        if rel.startswith(DB_PROXY_ALLOWED_PREFIXES) or rel in COMPOSITION_ROOTS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if "infrastructure" in parts:
                    idx = parts.index("infrastructure")
                    tail = parts[idx : idx + 2]
                    if tail == ["infrastructure", "persistence"]:
                        names = [a.name for a in node.names]
                if node.module.endswith("persistence.database"):
                    names = sorted({*names, "get_db_connection"})
            elif isinstance(node, ast.Import):
                for a in node.names:
                    parts = a.name.split(".")
                    if parts[:2] == ["comfyui_image_scorer", "infrastructure"] or "infrastructure.persistence" in a.name:
                        tail = parts[parts.index("infrastructure") :][:2] if "infrastructure" in parts else []
                        if tail == ["infrastructure", "persistence"]:
                            names.append(a.name)
            if names:
                violations.append(f"{rel}: persistence import {names}")
    assert not violations, "DB-proxy violations:\n" + "\n".join(violations)
