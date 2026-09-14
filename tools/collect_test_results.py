#!/usr/bin/env python3
"""Aggregate the latest build and test results of every image.

Reads the ``test-results/<run>/`` directories written by
``tools/test-all-images.sh`` (``<image>-build.jsonl`` and
``<image>-test.jsonl`` event streams) and writes one JSON document with, for
each image, its most recent run: the build stages, the test checks and the
resulting verdict.  Older runs whose test events were only printed to the
console can be imported from the console log with ``--from-log``.

The output (``data/test-results.json`` by default) is meant to be committed,
so that the website and the catalogue badges reflect verified results.\nVerdicts form a ladder: source-unavailable, source-available, built, runs, verified.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

RUN_ID = re.compile(r"^(\d{8})T(\d{6})Z$")
LOG_LINE = re.compile(r"^(ok|fail|skip|run|info)\s+(\S+)\s+(\S+)(?:\s+\((.*)\))?\s*$")
LOG_DIR = re.compile(r"Logs: (\S+/test-results/(\d{8}T\d{6}Z))")

BUILD_STAGES = "build"
TEST_CHECKS = "tests"


def run_date(run_id: str) -> str:
    match = RUN_ID.match(run_id)
    if not match:
        return run_id
    stamp = dt.datetime.strptime(run_id, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
    return stamp.isoformat().replace("+00:00", "Z")


def read_events(path: Path) -> list[dict]:
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def fold(events: list[dict], key: str) -> dict[str, dict]:
    """Keep the final status of each stage/check, in first-seen order."""
    result: dict[str, dict] = {}
    for event in events:
        name = event.get(key)
        status = event.get("status")
        if not name or status == "run":
            continue
        entry = {"status": status}
        if event.get("detail"):
            entry["detail"] = event["detail"]
        result[name] = entry
    return result


def scan_runs(root: Path) -> dict[str, dict[str, dict]]:
    """All build/test events per image and run, from the test-results tree."""
    runs: dict[str, dict[str, dict]] = {}
    for run_dir in sorted(p for p in root.iterdir() if p.is_dir() and RUN_ID.match(p.name)):
        for build_file in run_dir.glob("*-build.jsonl"):
            image = image_name(build_file.name, "-build.jsonl")
            record = {"run": run_dir.name, "date": run_date(run_dir.name),
                      BUILD_STAGES: fold(read_events(build_file), "stage")}
            test_file = run_dir / f"{build_file.name[: -len('-build.jsonl')]}-test.jsonl"
            if test_file.is_file():
                record[TEST_CHECKS] = fold(read_events(test_file), "check")
            runs.setdefault(image, {})[run_dir.name] = record
    return runs


def select_latest(runs: dict[str, dict[str, dict]]) -> dict[str, dict]:
    """Prefer the most recent run that reached the tests (a run interrupted
    after the build would otherwise hide an earlier complete verification)."""
    latest = {}
    for image, by_run in runs.items():
        ordered = [by_run[r] for r in sorted(by_run)]
        complete = [r for r in ordered if TEST_CHECKS in r or any(v["status"] == "fail" for v in r[BUILD_STAGES].values())]
        latest[image] = (complete or ordered)[-1]
    return latest


def image_name(file_name: str, suffix: str) -> str:
    """``kissat-3.1.0-2023-build.jsonl`` -> ``kissat-3.1.0:2023``."""
    stem = file_name[: -len(suffix)]
    solver, _, year = stem.rpartition("-")
    return f"{solver}:{year}"


def import_console_log(path: Path, runs: dict[str, dict[str, dict]]) -> int:
    """Fill test checks from a console log of tools/test-all-images.sh.

    Test events are attached to the image's record when the run directory
    named in the following ``Summary`` line matches the record's run.
    """
    pending: dict[str, dict[str, dict]] = {}
    imported = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LOG_LINE.match(line)
        if match:
            status, image, check, detail = match.groups()
            if status in {"run", "info"} or ":" not in image:
                continue
            entry = {"status": status}
            if detail:
                entry["detail"] = detail
            pending.setdefault(image, {})[check] = entry
            continue
        run = LOG_DIR.search(line)
        if run:
            run_id = run.group(2)
            for image, checks in pending.items():
                record = runs.get(image, {}).get(run_id)
                if record and TEST_CHECKS not in record:
                    # build stages are already in the record; keep only test checks
                    tests = {k: v for k, v in checks.items() if k not in record.get(BUILD_STAGES, {})}
                    if tests:
                        record[TEST_CHECKS] = tests
                        imported += 1
            pending = {}
    return imported


def verdict(record: dict) -> str:
    """Highest rung reached: source-unavailable < source-available < built < runs < verified."""
    stages = record.get(BUILD_STAGES, {})
    checks = record.get(TEST_CHECKS, {})
    failed = [k for k, v in stages.items() if v["status"] == "fail"]
    if any(k in ("source-download", "source-extract") for k in failed):
        return "source-unavailable"
    if failed:
        return "source-available"      # sources fetched, compilation or assembly failed
    if not checks:
        return "built"                 # image assembled, tests not run
    if checks.get("launch", {}).get("status") == "fail":
        return "built"
    if any(v["status"] == "fail" for v in checks.values()):
        return "runs"                  # launches, but some check failed
    return "verified"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--results-dir", type=Path, default=Path("test-results"))
    parser.add_argument("--from-log", action="append", default=[], type=Path,
                        help="console log of tools/test-all-images.sh to import test checks from")
    parser.add_argument("--output", type=Path, default=Path("data/test-results.json"))
    parser.add_argument("--merge", action="store_true",
                        help="keep images of the existing output that are not in test-results")
    args = parser.parse_args(argv)

    if not args.results_dir.is_dir():
        print(f"[ERROR] no such directory: {args.results_dir}", file=sys.stderr)
        return 1
    runs = scan_runs(args.results_dir)
    for log in args.from_log:
        print(f"[OK] imported test checks from {log}: {import_console_log(log, runs)} image(s)")
    latest = select_latest(runs)
    for record in latest.values():
        record["verdict"] = verdict(record)

    if args.merge and args.output.is_file():
        previous = json.loads(args.output.read_text(encoding="utf-8")).get("images", {})
        for image, record in previous.items():
            if image not in latest:
                latest[image] = record

    document = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "images": dict(sorted(latest.items())),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    counts = {}
    for record in latest.values():
        counts[record["verdict"]] = counts.get(record["verdict"], 0) + 1
    print(f"[OK] {len(latest)} image(s) written to {args.output}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
