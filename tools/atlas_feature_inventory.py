"""Atlas feature-creep inventory, AST-only. No imports or effects.

Classification is evidence, NOT permission to delete a module. Dynamically
loaded plugins, shell entrypoints and files referenced outside this directory
require separate physical audits.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import sys


def _imports(tree: ast.AST) -> set[str]:
    names = set()
    for item in ast.walk(tree):
        if isinstance(item, ast.ImportFrom):
            if item.module:
                names.add(item.module.split(".")[-1])
            if item.level:
                names.update(a.name for a in item.names if a.name != "*")
        elif isinstance(item, ast.Import):
            for alias in item.names:
                segments = alias.name.split(".")
                if len(segments) > 1 and "atlas" in segments:
                    names.add(segments[-1])
        elif isinstance(item, ast.Call) and item.args:
            func = item.func
            if isinstance(func, ast.Attribute) and func.attr == "import_module":
                argument = item.args[0]
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    names.add(argument.value.split(".")[-1])
    return names


def inventory(root: Path) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("invalid_atlas_root")
    modules = sorted(p for p in root.glob("*.py") if p.is_file())
    if not modules or len(modules) > 500:
        raise ValueError("invalid_module_count")
    for p in modules:
        if p.is_symlink():
            raise ValueError("symlinked_source_forbidden")
    all_names = {p.stem for p in modules}
    reverse = {name: set() for name in all_names}
    errors = []
    for p in modules:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8-sig"), filename=p.name)
            for dep in _imports(tree) & all_names:
                if dep != p.stem:
                    reverse[dep].add(p.name)
        except (SyntaxError, UnicodeError):
            errors.append(p.name)
    launch = []
    for ext in ("*.service", "*.timer", "*.sh"):
        launch.extend(p for p in root.glob(ext) if p.is_file() and not p.is_symlink())
    launch_text = "\n".join(p.read_text(encoding="utf-8-sig", errors="replace") for p in launch)
    output = []
    for name in sorted(all_names):
        label = "REFERENCED"
        entrypoint = bool(re.search(r"(?<![\w.])(?:atlas\.)?" + re.escape(name) + r"(?![\w.])", launch_text))
        if entrypoint:
            label = "ENTRYPOINT_REFERENCED"
        elif not reverse[name]:
            label = "REVIEW_DYNAMIC_OR_LEGACY"
        output.append({"module": name + ".py", "classification": label,
                       "direct_importers": sorted(reverse[name]),
                       "service_or_script_reference": entrypoint})
    flags = []
    for config in sorted(root.glob("config*.json")):
        if config.is_symlink():
            raise ValueError("symlinked_config_forbidden")
        data = json.loads(config.read_text(encoding="utf-8-sig"))
        def walk(obj, prefix=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    attr = f"{prefix}.{key}" if prefix else key
                    if isinstance(value, bool):
                        flags.append({"config": config.name, "flag": attr, "enabled": value})
                    elif isinstance(value, dict):
                        walk(value, attr)
        walk(data)
    return {"schema_version": 1, "source_modules": len(modules),
            "syntax_errors": errors, "modules": output, "feature_flags": flags,
            "warning": "No import/reference does not imply unused; investigate runtime consumers before removal."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        data = inventory(args.source)
    except (OSError, ValueError):
        print('{"status":"DENIED_INVALID_INPUT"}')
        return 2
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if not data["syntax_errors"] else 2


if __name__ == "__main__":
    sys.exit(main())
