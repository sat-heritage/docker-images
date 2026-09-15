#!/usr/bin/env python3
"""Fill the ``license`` field of <set>/solvers.json from the archived sources.

For every entry of the requested sets, the source archive named by its
download_url is fetched (a local mirror directory is used first, then a
download cache), and scanned for licence files (LICENSE, COPYING, ...) and,
failing that, for licence headers in the source files.  The result is written
as an SPDX-like identifier (MIT, GPL-3.0, BSD-3-Clause, ...; several are joined
with " AND ") together with ``license_source``, which says where it was read.
Entries that already have a licence are left alone unless --overwrite.

Usage: detect_licenses.py [--repo .] [--set 2011 ...] [--mirror DIR ...] [--cache DIR] [--overwrite] [--dry-run]
"""
import argparse
import io
import json
import re
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

RELEASES = "https://github.com/sat-heritage/docker-images/releases/download/"
LICENSE_FILE = re.compile(r"(^|/)(license|licence|copying|copyright|legal|notice)([._-].*)?(\.txt|\.md)?$", re.I)
SOURCE_FILE = re.compile(r"\.(c|cc|cpp|cxx|h|hh|hpp|java|py|ml|hs|scala|cs)$", re.I)
PATTERNS = [
    ("MIT", re.compile(r"Permission is hereby granted, free of charge", re.I)),
    ("GPL-3.0", re.compile(r"GNU (GENERAL )?PUBLIC LICENSE\s+Version 3|GNU General Public License as published by[^.]*version 3|GPLv3", re.I)),
    ("GPL-2.0", re.compile(r"GNU (GENERAL )?PUBLIC LICENSE\s+Version 2|GNU General Public License as published by[^.]*version 2|GPLv2", re.I)),
    ("LGPL-3.0", re.compile(r"GNU LESSER GENERAL PUBLIC LICENSE\s+Version 3|Lesser General Public License[^.]*version 3", re.I)),
    ("LGPL-2.1", re.compile(r"GNU LESSER GENERAL PUBLIC LICENSE\s+Version 2\.1|Lesser General Public License[^.]*version 2\.1", re.I)),
    ("LGPL-2.0", re.compile(r"GNU LIBRARY GENERAL PUBLIC LICENSE|Library General Public License", re.I)),
    ("EPL-1.0", re.compile(r"Eclipse Public License", re.I)),
    ("Apache-2.0", re.compile(r"Apache License,? Version 2", re.I)),
    ("BSD-3-Clause", re.compile(r"Redistribution and use in source and binary forms.{0,900}Neither the name", re.I | re.S)),
    ("BSD-2-Clause", re.compile(r"Redistribution and use in source and binary forms", re.I)),
    ("MPL-2.0", re.compile(r"Mozilla Public License,? v(ersion)? 2", re.I)),
    ("Unlicense", re.compile(r"This is free and unencumbered software released into the public domain", re.I)),
    ("CC-BY-4.0", re.compile(r"Creative Commons Attribution 4", re.I)),
]


def identify(text: str) -> str | None:
    for name, rx in PATTERNS:
        if rx.search(text):
            return name
    return None


def members(path: Path):
    """(name, read_head) pairs for the files of an archive; unreadable archives yield nothing."""
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                for info in z.infolist():
                    if not info.is_dir() and info.file_size < 4_000_000:
                        yield info.filename, lambda i=info, z=z: z.open(i).read(8000)
        elif tarfile.is_tarfile(path):
            with tarfile.open(path) as t:
                for m in t:
                    if m.isfile() and m.size < 4_000_000:
                        yield m.name, lambda m=m, t=t: t.extractfile(m).read(8000)
    except Exception as e:
        print(f"[!!] {path.name}: {e}", file=sys.stderr)


def scan(path: Path) -> tuple[str | None, str]:
    """Licences of an archive: from its licence files, else from the headers of its source files."""
    found, headers = {}, {}
    inner = []
    for name, read in members(path):
        base = name.rsplit("/", 1)[-1]
        if LICENSE_FILE.search(name) and not SOURCE_FILE.search(base):
            lic = identify(read().decode("utf-8", "replace"))
            found.setdefault(lic or "unrecognized", name)
        elif SOURCE_FILE.search(base) and len(headers) < 400:
            lic = identify(read().decode("utf-8", "replace")[:3000])
            if lic:
                headers.setdefault(lic, name)
        elif base.endswith((".tar.gz", ".tgz", ".zip", ".tar.xz", ".tar.bz2")) and len(inner) < 6:
            inner.append((name, read))
    known = [k for k in found if k != "unrecognized"]
    if known:
        return " AND ".join(sorted(known)), "licence file " + ", ".join(found[k] for k in sorted(known))
    if headers:
        return " AND ".join(sorted(headers)), "licence header of " + ", ".join(headers[k] for k in sorted(headers))
    if "unrecognized" in found:
        return None, f"unrecognized licence file {found['unrecognized']}"
    return None, ""


class _Vars(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def asset_of(entry_set: str, key: str, entry: dict, setup: dict) -> str | None:
    """The download URL of an entry, with the same placeholders as satex (SOLVER_NAME, SOLVER, ENTRY, VERSION)."""
    block = setup.get(key) if isinstance(setup.get(key), dict) else {}
    url = block.get("download_url") or setup.get("download_url")
    if not url:
        return None
    url = url.format_map(_Vars(SOLVER_NAME=entry.get("name", key), SOLVER=key, ENTRY=entry_set, VERSION=str(entry.get("version", ""))))
    return None if "{" in url else url


def fetch(url: str, mirrors: list[Path], cache: Path) -> Path | None:
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1].split("?")[0])
    for m in mirrors:
        for cand in (m / name, *(m.glob(f"*/{name}"))):
            if cand.is_file():
                return cand
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / (urllib.parse.quote(url.split("/download/")[-1], safe="") if "/download/" in url else name)
    if target.is_file():
        return target
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                target.write_bytes(r.read())
            time.sleep(1.0 if "zenodo" in url else 0.2)   # Zenodo throttles guests hard
            return target
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 5:
                time.sleep(60 * (attempt + 1))
                continue
            print(f"[!!] {url}: {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"[!!] {url}: {e}", file=sys.stderr)
            return None
    return None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--set", action="append", default=[], help="year to process (default: every set of index.json)")
    p.add_argument("--mirror", action="append", type=Path, default=[], help="directory (or its subdirectories) holding archives already downloaded")
    p.add_argument("--cache", type=Path, default=Path("source-cache"))
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    sets = a.set or [str(s) for s in json.loads((a.repo / "index.json").read_text())]
    results = {}
    for entry_set in sets:
        sfile = a.repo / entry_set / "solvers.json"
        if not sfile.is_file():
            continue
        text = sfile.read_text()
        indent = len(re.search(r"\n( +)\"", text).group(1)) if re.search(r"\n( +)\"", text) else 2
        solvers = json.loads(text)
        setup = json.loads((a.repo / entry_set / "setup.json").read_text()) if (a.repo / entry_set / "setup.json").is_file() else {}
        changed = 0
        for key, entry in solvers.items():
            if entry.get("license") and not a.overwrite:
                continue
            url = asset_of(entry_set, key, entry, setup)
            if not url:
                continue
            if url not in results:
                path = fetch(url, a.mirror, a.cache)
                results[url] = scan(path) if path else (None, "archive not available")
            lic, source = results[url]
            if lic:
                entry["license"] = lic
                entry["license_source"] = source
                changed += 1
            elif source:
                entry.setdefault("license_source", source)
            print(f"{key}:{entry_set:6s} {lic or '-':22s} {source[:90]}")
        if changed and not a.dry_run:
            sfile.write_text(json.dumps(solvers, indent=indent, ensure_ascii=False) + "\n")
        print(f"[OK] {entry_set}: {changed} entries given a licence out of {len(solvers)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
