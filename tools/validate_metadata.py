#!/usr/bin/env python3
"""Validate every registry JSON document against its published schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    sys.exit("jsonschema is required; install requirements-dev.txt")


ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"


def load(path: Path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def validate(path: Path, schema_path: Path) -> list[str]:
    validator = jsonschema.Draft202012Validator(load(schema_path))
    errors = sorted(
        validator.iter_errors(load(path)), key=lambda error: list(error.path)
    )
    messages = []
    for error in errors:
        location = "/".join(str(item) for item in error.absolute_path) or "<root>"
        messages.append(f"{path.relative_to(ROOT)}:{location}: {error.message}")
    return messages


def unlisted_sets() -> list[str]:
    """Directories that hold a registry but are missing from index.json.

    A set absent from the index is invisible to satex and to the website, while
    its files stay valid on their own, so nothing else catches the omission.
    """
    listed = {str(entry) for entry in load(ROOT / "index.json")}
    found = sorted(
        path.parent.name
        for path in ROOT.glob("*/solvers.json")
        if path.parent.name not in listed
    )
    return found


def main() -> int:
    messages = [f"index.json: {name} holds a solvers.json but is not listed"
                for name in unlisted_sets()]
    messages += validate(ROOT / "index.json", SCHEMAS / "index.schema.json")
    for entry in load(ROOT / "index.json"):
        entry_dir = ROOT / str(entry)
        messages.extend(
            validate(entry_dir / "solvers.json", SCHEMAS / "solvers.schema.json")
        )
        messages.extend(
            validate(entry_dir / "setup.json", SCHEMAS / "setup.schema.json")
        )
    if messages:
        print("\n".join(messages), file=sys.stderr)
        return 1
    print("metadata: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
