#!/usr/bin/env python3
"""Normalize legacy solver status strings without reformatting JSON files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

STATUS_LINE = re.compile(r'^(\s*)"status"\s*:\s*("(?:[^"\\]|\\.)*")(,?)\s*$')
DETAIL_LINE = re.compile(r'^(\s*)"status_detail"\s*:\s*("(?:[^"\\]|\\.)*")(,?)\s*$')


def canonical_status(status: str) -> str:
    lowered = status.lower()
    if lowered in {"ok", "unknown", "unstable", "fixme"}:
        return lowered
    return "fixme"


def normalize_file(path: Path, write: bool) -> bool:
    changed = False
    output: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    restored: list[str] = []
    index = 0
    while index < len(lines):
        status_match = STATUS_LINE.match(lines[index].rstrip("\r\n"))
        detail_match = None
        if index + 1 < len(lines):
            detail_match = DETAIL_LINE.match(lines[index + 1].rstrip("\r\n"))
        if status_match and detail_match:
            status = json.loads(status_match.group(2))
            detail = json.loads(detail_match.group(2))
            if status == "fixme" and detail == "unknown":
                newline = "\r\n" if lines[index].endswith("\r\n") else "\n"
                restored.append(
                    f'{status_match.group(1)}"status": "unknown"'
                    f"{detail_match.group(3)}{newline}"
                )
                changed = True
                index += 2
                continue
        restored.append(lines[index])
        index += 1
    lines = restored
    for index, line in enumerate(lines):
        stripped = line.rstrip("\r\n")
        if stripped.rstrip().endswith(","):
            next_content = next(
                (
                    candidate.strip()
                    for candidate in lines[index + 1 :]
                    if candidate.strip()
                ),
                "",
            )
            if next_content.startswith("}"):
                ending = "\r\n" if line.endswith("\r\n") else "\n"
                line = stripped.rstrip()[:-1] + ending
                changed = True
        match = STATUS_LINE.match(line.rstrip("\r\n"))
        if not match:
            output.append(line)
            continue
        indent, encoded_status, comma = match.groups()
        status = json.loads(encoded_status)
        canonical = canonical_status(status)
        newline = "\r\n" if line.endswith("\r\n") else "\n"
        detail_needed = status != canonical
        status_comma = "," if detail_needed else comma
        output.append(
            f'{indent}"status": {json.dumps(canonical)}{status_comma}{newline}'
        )
        if detail_needed:
            output.append(
                f'{indent}"status_detail": {json.dumps(status)}{comma}{newline}'
            )
            changed = True
        elif encoded_status != json.dumps(canonical):
            changed = True
    if changed and write:
        path.write_text("".join(output), encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="update files in place")
    args = parser.parse_args()
    changed = [
        path
        for path in sorted(Path.cwd().glob("*/solvers.json"))
        if normalize_file(path, args.write)
    ]
    for path in changed:
        print(path)
    return 0 if args.write or not changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
