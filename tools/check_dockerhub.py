#!/usr/bin/env python3
"""List which images of the catalogue are published on Docker Hub, as data/dockerhub.json.

The candidate repositories are the solver keys of every set listed in index.json
(the images are named satex/<key>:<set>).  Their tags are read from the registry
API, which needs one anonymous token per repository and is not rate limited for
tag listings, unlike the Docker Hub web API whose anonymous listing stops at the
first page.  A repository that does not exist yields no tags.

Usage: check_dockerhub.py [--repo .] [--namespace satex] [--output data/dockerhub.json] [--workers 8]
"""
import argparse
import concurrent.futures
import datetime
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN = "https://auth.docker.io/token?service=registry.docker.io&scope=repository:{ns}/{repo}:pull"
TAGS = "https://registry-1.docker.io/v2/{ns}/{repo}/tags/list"
UA = {"User-Agent": "sat-heritage-site"}


def get_json(url: str, headers: dict | None = None, retries: int = 4):
    """GET a JSON document; 404 means absent, other failures are retried with growing pauses."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (401, 404):
                return None
            if attempt == retries - 1:
                raise
            time.sleep(10 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"unreachable: {url}")


def list_tags(ns: str, repo: str) -> list[str] | None:
    """Tags of ns/repo, or None when the repository does not exist."""
    token = get_json(TOKEN.format(ns=ns, repo=urllib.parse.quote(repo)))
    if not token:
        return None
    data = get_json(TAGS.format(ns=ns, repo=urllib.parse.quote(repo)), {"Authorization": f"Bearer {token['token']}"})
    if data is None:
        return None
    return sorted(data.get("tags") or [])


def catalogue_keys(repo: Path) -> dict[str, set[str]]:
    """solver key -> sets (years) in which it appears."""
    keys: dict[str, set[str]] = {}
    for entry in json.loads((repo / "index.json").read_text()):
        f = repo / str(entry) / "solvers.json"
        if f.is_file():
            for k in json.loads(f.read_text()):
                keys.setdefault(k, set()).add(str(entry))
    return keys


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--namespace", default="satex")
    p.add_argument("--output", default="data/dockerhub.json")
    p.add_argument("--workers", type=int, default=8)
    a = p.parse_args(argv)
    keys = catalogue_keys(a.repo)
    print(f"[..] {len(keys)} candidate repositories under {a.namespace}", file=sys.stderr)
    repositories, errors = [], 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        for name, tags in zip(sorted(keys), pool.map(lambda k: _safe(a.namespace, k), sorted(keys))):
            if tags == "error":
                errors += 1
                continue
            if tags is not None:
                repositories.append({"name": name, "tags": tags})
    images = sorted(f"{r['name']}:{t}" for r in repositories for t in r["tags"])
    expected = {f"{k}:{y}" for k, ys in keys.items() for y in ys}
    doc = {"generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "namespace": a.namespace,
           "images": [f"{a.namespace}/{i}" for i in images], "repositories": repositories}
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    with open(a.output, "w") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print(f"[OK] {len(repositories)} repositories, {len(images)} image tags, {len(expected & set(images))} of the {len(expected)} catalogue images published; "
          f"{errors} lookup error(s); written to {a.output}", file=sys.stderr)
    return 1 if errors > len(keys) // 10 else 0


def _safe(ns: str, key: str):
    try:
        return list_tags(ns, key)
    except Exception as e:  # one failing lookup must not abort the inventory
        print(f"[!!] {key}: {e}", file=sys.stderr)
        return "error"


if __name__ == "__main__":
    raise SystemExit(main())
