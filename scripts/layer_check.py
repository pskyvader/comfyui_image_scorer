import ast
from pathlib import Path

ROOT = Path(".").resolve()
LAYERS = ("core", "domain", "application", "adapters", "infrastructure")
ALLOWED = {
    "core": (),
    "domain": ("core",),
    "application": ("core", "domain"),
    "adapters": ("core", "domain", "application"),
    "infrastructure": ("core", "domain"),
}
bad = []
for layer in LAYERS:
    for p in sorted((ROOT / layer).rglob("*.py")):
        if "comfyui_image_scorer_old" in str(p) or "typings" in str(p):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf8"))
        except Exception:
            continue
        for node in ast.walk(tree):

            def resolve(node):
                if isinstance(node, ast.ImportFrom):
                    if node.level > 0:
                        n = node.level - 1
                        base = list(p.relative_to(ROOT).parts[:-1])
                        if n > len(base):
                            return None
                        parts = base[: len(base) - n] + (
                            node.module.split(".") if node.module else []
                        )
                    elif node.module:
                        parts = node.module.split(".")
                    else:
                        return None
                elif isinstance(node, ast.Import):
                    parts = node.names[0].name.split(".")
                else:
                    return None
                if parts and parts[0] in LAYERS:
                    return parts[0]
                return None

            t = resolve(node)
            if t and t != layer and t not in ALLOWED[layer]:
                bad.append(f"{p.relative_to(ROOT)}: {layer} -> {t} (L{node.lineno})")

print("\n".join(sorted(bad)) or "CLEAN")
