#!/usr/bin/env python3
"""Collect usage counters for the website, as data/stats.json (generated, not versioned).

- Docker Hub pull counts of every repository of the namespace: the repository
  listing is paginated only for logged-in users, so DOCKER_USERNAME and
  DOCKER_PASSWORD (the secrets of the image workflows) are used when present;
  without them only the first page (100 repositories) is read.
- GitHub download counts of every release asset (public API).

Both counters include the project's own builds and verification runs.

Usage: collect_stats.py [--namespace satex] [--repo sat-heritage/docker-images] [--output data/stats.json]
"""
import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "sat-heritage-site"}


def get_json(url: str, headers: dict | None = None, data: bytes | None = None, retries: int = 4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})}, data=data)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403) and data is None and attempt == 0:
                return None   # not allowed anonymously: the caller degrades gracefully
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(15 * (attempt + 1))
                continue
            if attempt == retries - 1:
                print(f"[!!] {url}: {e}", file=sys.stderr)
                return None
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                return None
            time.sleep(5)
    return None


def docker_hub_pulls(namespace: str) -> dict[str, dict]:
    headers = {}
    user, password = os.environ.get("DOCKER_USERNAME"), os.environ.get("DOCKER_PASSWORD")
    if user and password:
        tok = get_json("https://hub.docker.com/v2/users/login/", {"Content-Type": "application/json"},
                       json.dumps({"username": user, "password": password}).encode())
        if tok and tok.get("token"):
            headers = {"Authorization": f"JWT {tok['token']}"}
        else:
            print("[!!] Docker Hub login failed, reading the first page only", file=sys.stderr)
    out, url = {}, f"https://hub.docker.com/v2/repositories/{namespace}/?page_size=100"
    while url:
        page = get_json(url, headers)
        if not page:
            break
        for r in page.get("results", []):
            out[r["name"]] = {"pulls": r.get("pull_count", 0), "stars": r.get("star_count", 0), "updated": r.get("last_updated")}
        url = page.get("next")
        if url and not headers:
            print("[..] anonymous access: only the first page of repositories is readable", file=sys.stderr)
            break
    return out


def github_downloads(repo: str) -> dict[str, dict]:
    out, page = {}, 1
    headers = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"} if os.environ.get("GITHUB_TOKEN") else {}
    while True:
        rs = get_json(f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}", headers)
        if not rs:
            break
        for r in rs:
            for a in r.get("assets", []):
                out[f"{r['tag_name']}/{a['name']}"] = {"downloads": a.get("download_count", 0), "size": a.get("size", 0)}
        if len(rs) < 100:
            break
        page += 1
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--namespace", default="satex")
    p.add_argument("--repo", default="sat-heritage/docker-images")
    p.add_argument("--output", default="data/stats.json")
    a = p.parse_args(argv)
    pulls = docker_hub_pulls(a.namespace)
    downloads = github_downloads(a.repo)
    doc = {"generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "docker_hub": {"namespace": a.namespace, "complete": len(pulls) > 100 or bool(os.environ.get("DOCKER_USERNAME")), "repositories": pulls},
           "github_releases": {"repository": a.repo, "assets": downloads}}
    os.makedirs(os.path.dirname(a.output) or ".", exist_ok=True)
    with open(a.output, "w") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print(f"[OK] {len(pulls)} Docker Hub repositories ({sum(v['pulls'] for v in pulls.values())} pulls), "
          f"{len(downloads)} release assets ({sum(v['downloads'] for v in downloads.values())} downloads) written to {a.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
