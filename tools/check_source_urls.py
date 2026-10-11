#!/usr/bin/env python3
"""Check that every archive a recipe downloads is actually reachable.

An image can build on a developer machine and still fail in the workflows: a
local download cache (SATEX_SOURCE_MIRROR) serves archives that were never
published, so the recipe looks fine until GitHub Actions asks the real URL for
it.  This script resolves the download URL of every entry of every set, asks
each distinct URL for its first byte, and reports the ones that answer with
anything but success.

    tools/check_source_urls.py                 # every set of index.json
    tools/check_source_urls.py 2009 2010       # only these sets
    tools/check_source_urls.py --verbose       # list the reachable ones too

The exit status is non-zero when at least one URL is missing, so the script can
guard a commit or run as a workflow of its own.  It never downloads a whole
archive: it sends a ranged request for one byte, exactly as satex.py does when
it probes sources before a build.

Archive hosts rate-limit such sweeps, Zenodo in particular, and a throttled
answer is not a missing archive.  Requests to one host are therefore spaced out
and retried, and a URL still throttled at the end is reported as undetermined
rather than missing.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 30
USER_AGENT = "satex-source-check"
RETRY_STATUS = {429, 500, 502, 503, 504}


def load(path: Path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def source_urls(entry_dir: Path) -> dict[str, str]:
    """Return the download URL of every solver of one set, keyed by solver."""
    setup = load(entry_dir / "setup.json")
    solvers = load(entry_dir / "solvers.json")
    default = setup.get("download_url")
    urls = {}
    for key, entry in solvers.items():
        if not isinstance(entry, dict):
            continue
        override = setup.get(key) if isinstance(setup.get(key), dict) else {}
        template = override.get("download_url", default)
        if not template:
            continue
        urls[key] = (
            template.replace("{SOLVER_NAME}", entry.get("name", key))
            .replace("{SOLVER}", key)
            .replace("{VERSION}", str(entry.get("version", "")))
        )
    return urls


def probe(url: str, delay: float, attempts: int) -> tuple[str, str]:
    """Ask for the first byte of url.

    Returns one of "ok", "missing" or "undetermined", with the detail to print.
    A throttled or temporarily failing host is retried, waiting for its
    Retry-After when it sends one, and reported as undetermined if it never
    answers.
    """
    request = urllib.request.Request(
        url, headers={"Range": "bytes=0-0", "User-Agent": USER_AGENT}
    )
    detail = "no answer"
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return "ok", f"HTTP {response.status}"
        except urllib.error.HTTPError as error:
            detail = f"HTTP {error.code}"
            if error.code not in RETRY_STATUS:
                return "missing", detail
            wait = error.headers.get("Retry-After") if error.headers else None
            pause = float(wait) if wait and wait.isdigit() else delay * 4 * attempt
        except urllib.error.URLError as error:
            detail = str(error.reason)
            pause = delay * 4 * attempt
        except Exception as error:  # a malformed URL, a reset connection
            return "undetermined", str(error)
        if attempt < attempts:
            time.sleep(pause)
    return "undetermined", f"{detail} after {attempts} attempts"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sets", nargs="*", help="sets to check (default: all of index.json)")
    parser.add_argument("-v", "--verbose", action="store_true", help="also list reachable URLs")
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="seconds to wait between two requests to the same host (default: 1)",
    )
    parser.add_argument(
        "--attempts", type=int, default=4, help="tries per URL when throttled (default: 4)"
    )
    args = parser.parse_args()

    wanted = args.sets or [str(entry) for entry in load(ROOT / "index.json")]
    seen: dict[str, tuple[str, str]] = {}
    last_request: dict[str, float] = {}
    missing = []
    undetermined = []
    total = 0

    for name in wanted:
        entry_dir = ROOT / name
        if not (entry_dir / "solvers.json").is_file():
            print(f"{name}: no solvers.json, skipped", file=sys.stderr)
            continue
        for key, url in sorted(source_urls(entry_dir).items()):
            total += 1
            if url not in seen:
                host = urllib.parse.urlparse(url).netloc
                since = time.monotonic() - last_request.get(host, 0.0)
                if since < args.delay:
                    time.sleep(args.delay - since)
                seen[url] = probe(url, args.delay, args.attempts)
                last_request[host] = time.monotonic()
            state, detail = seen[url]
            if state == "ok":
                if args.verbose:
                    print(f"ok      {name}/{key}: {detail}")
            elif state == "missing":
                missing.append((name, key, detail, url))
                print(f"missing {name}/{key}: {detail} {url}")
            else:
                undetermined.append((name, key, detail, url))
                print(f"unknown {name}/{key}: {detail} {url}")

    print(
        f"{total} entries, {len(seen)} distinct URLs, "
        f"{len(missing)} missing, {len(undetermined)} undetermined",
        file=sys.stderr,
    )
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
