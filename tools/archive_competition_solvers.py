#!/usr/bin/env python3
"""Mirror solver bundles from a competition archive to a GitHub release.

The competition archive is never modified.  Each top-level solver directory is
copied into a deterministic ``.tar.xz`` asset so that the Docker recipes can
download one solver without fetching the complete competition distribution.
Publishing is opt-in through ``--upload``.
"""

from __future__ import annotations

import argparse
import calendar
import copy
import hashlib
import json
import mimetypes
import os
import posixpath
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterable


API_ROOT = "https://api.github.com"
UPLOAD_ROOT = "https://uploads.github.com"
DEFAULT_REPOSITORY = "sat-heritage/docker-images"
IGNORED_ROOTS = {"__MACOSX"}


class ArchiveError(RuntimeError):
    """The source archive cannot be mirrored safely."""


class GitHubError(RuntimeError):
    """A GitHub API operation failed."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_member_name(name: str) -> str:
    """Return a safe POSIX archive path, rejecting traversal and absolute paths."""

    name = name.replace("\\", "/")
    while name.startswith("./"):
        name = name[2:]
    path = PurePosixPath(name)
    if not name or path.is_absolute() or any(part in {"", ".."} for part in path.parts):
        raise ArchiveError(f"unsafe archive member: {name!r}")
    return path.as_posix().rstrip("/")


def member_root(name: str) -> str | None:
    normalized = normalized_member_name(name)
    parts = PurePosixPath(normalized).parts
    if len(parts) < 2 or parts[0] in IGNORED_ROOTS or parts[0].startswith("."):
        return None
    return parts[0]


def validate_link(member_name: str, link_name: str) -> None:
    if not link_name:
        raise ArchiveError(f"empty link target in {member_name!r}")
    link_name = link_name.replace("\\", "/")
    if PurePosixPath(link_name).is_absolute():
        raise ArchiveError(f"absolute link target in {member_name!r}: {link_name!r}")
    root = PurePosixPath(member_name).parts[0]
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(member_name), link_name))
    if resolved != root and not resolved.startswith(root + "/"):
        raise ArchiveError(f"link escapes solver directory: {member_name!r} -> {link_name!r}")


class SolverArchive:
    def __init__(self, path: Path):
        self.path = path
        if zipfile.is_zipfile(path):
            self.kind = "zip"
        elif tarfile.is_tarfile(path):
            self.kind = "tar"
        else:
            raise ArchiveError(f"unsupported archive format: {path}")

    def roots(self) -> list[str]:
        roots: set[str] = set()
        if self.kind == "zip":
            with zipfile.ZipFile(self.path) as archive:
                names = (member.filename for member in archive.infolist())
                for name in names:
                    root = member_root(name)
                    if root:
                        roots.add(root)
        else:
            with tarfile.open(self.path, "r:*") as archive:
                for member in archive.getmembers():
                    root = member_root(member.name)
                    if root:
                        roots.add(root)
        return sorted(roots, key=str.casefold)

    def output_format(self, requested: str) -> str:
        if requested == "auto":
            return "zip" if self.kind == "zip" else "tar.xz"
        return requested

    def write_solver(self, solver: str, destination: Path, output_format: str) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.unlink(missing_ok=True)
        try:
            if output_format == "zip":
                count = self._write_solver_zip(temporary, solver)
            else:
                with tarfile.open(temporary, "w:xz", format=tarfile.PAX_FORMAT) as output:
                    root = tarfile.TarInfo(solver)
                    root.type = tarfile.DIRTYPE
                    root.mode = 0o755
                    root.mtime = 0
                    output.addfile(root)
                    if self.kind == "zip":
                        count = self._write_zip_solver_to_tar(output, solver)
                    else:
                        count = self._write_tar_solver_to_tar(output, solver)
            if count == 0:
                raise ArchiveError(f"solver directory not found: {solver!r}")
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def _write_solver_zip(self, destination: Path, solver: str) -> int:
        if self.kind != "zip":
            raise ArchiveError(
                "ZIP output from a TAR source is not supported; use --format tar.xz"
            )
        count = 0
        with zipfile.ZipFile(self.path) as source, zipfile.ZipFile(destination, "w") as output:
            root = zipfile.ZipInfo(solver + "/")
            root.date_time = (1980, 1, 1, 0, 0, 0)
            root.create_system = 3
            root.external_attr = (stat.S_IFDIR | 0o755) << 16
            output.writestr(root, b"")
            members = sorted(source.infolist(), key=lambda member: member.filename)
            for member in members:
                name = normalized_member_name(member.filename)
                if name == solver:
                    continue
                if not name.startswith(solver + "/"):
                    continue
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    validate_link(name, source.read(member).decode("utf-8"))
                info = copy.copy(member)
                info.filename = name + ("/" if member.is_dir() else "")
                output.writestr(info, source.read(member))
                count += 1
        return count

    def _write_zip_solver_to_tar(self, output: tarfile.TarFile, solver: str) -> int:
        count = 0
        with zipfile.ZipFile(self.path) as source:
            members = sorted(source.infolist(), key=lambda member: member.filename)
            for member in members:
                name = normalized_member_name(member.filename)
                if name == solver:
                    continue
                if not name.startswith(solver + "/"):
                    continue
                mode = member.external_attr >> 16
                info = tarfile.TarInfo(name)
                info.mtime = calendar.timegm(member.date_time + (0, 0, -1))
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                if member.is_dir():
                    info.type = tarfile.DIRTYPE
                    info.mode = stat.S_IMODE(mode) or 0o755
                    output.addfile(info)
                elif stat.S_ISLNK(mode):
                    target = source.read(member).decode("utf-8")
                    validate_link(name, target)
                    info.type = tarfile.SYMTYPE
                    info.mode = stat.S_IMODE(mode) or 0o777
                    info.linkname = target
                    output.addfile(info)
                else:
                    info.type = tarfile.REGTYPE
                    info.mode = stat.S_IMODE(mode) or 0o644
                    info.size = member.file_size
                    with source.open(member) as contents:
                        output.addfile(info, contents)
                count += 1
        return count

    def _write_tar_solver_to_tar(self, output: tarfile.TarFile, solver: str) -> int:
        count = 0
        with tarfile.open(self.path, "r:*") as source:
            members = sorted(source.getmembers(), key=lambda member: member.name)
            for original in members:
                name = normalized_member_name(original.name)
                if name == solver:
                    continue
                if not name.startswith(solver + "/"):
                    continue
                if original.isdev() or original.isfifo():
                    raise ArchiveError(f"unsupported special file: {name!r}")
                info = copy.copy(original)
                info.name = name
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                if info.issym():
                    validate_link(name, info.linkname)
                elif info.islnk():
                    target = normalized_member_name(info.linkname)
                    if target != solver and not target.startswith(solver + "/"):
                        raise ArchiveError(f"hard link escapes solver directory: {name!r}")
                    info.linkname = target
                contents: BinaryIO | None = source.extractfile(original) if info.isfile() else None
                output.addfile(info, contents)
                count += 1
        return count


def download_source(source: str, destination: Path) -> dict[str, object]:
    parsed = urllib.parse.urlparse(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if parsed.scheme in {"http", "https"}:
        request = urllib.request.Request(source, headers={"User-Agent": "sat-heritage-archiver"})
        with urllib.request.urlopen(request) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    elif parsed.scheme == "file":
        shutil.copyfile(urllib.request.url2pathname(parsed.path), destination)
    elif parsed.scheme:
        raise ArchiveError(f"unsupported source URL scheme: {parsed.scheme}")
    else:
        shutil.copyfile(Path(source).expanduser(), destination)
    return {
        "source": source,
        "size": destination.stat().st_size,
        "sha256": sha256_file(destination),
    }


class GitHubRelease:
    def __init__(self, repository: str, token: str):
        if repository.count("/") != 1:
            raise GitHubError("repository must have the form owner/name")
        self.repository = repository
        self.token = token

    def _request(
        self,
        method: str,
        url: str,
        body: bytes | None = None,
        content_type: str = "application/vnd.github+json",
    ) -> object | None:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "Content-Type": content_type,
            "User-Agent": "sat-heritage-archiver",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request) as response:
                payload = response.read()
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(detail).get("message", detail)
            except json.JSONDecodeError:
                pass
            raise GitHubError(f"GitHub API {error.code}: {detail}", error.code) from error
        if not payload:
            return None
        return json.loads(payload)

    def release(self, tag: str) -> dict[str, object] | None:
        tag_path = urllib.parse.quote(tag, safe="")
        url = f"{API_ROOT}/repos/{self.repository}/releases/tags/{tag_path}"
        try:
            result = self._request("GET", url)
        except GitHubError as error:
            if error.status == 404:
                return None
            raise
        assert isinstance(result, dict)
        return result

    def create_release(
        self, tag: str, name: str, body: str, target: str | None
    ) -> dict[str, object]:
        payload: dict[str, object] = {"tag_name": tag, "name": name, "body": body}
        if target:
            payload["target_commitish"] = target
        result = self._request(
            "POST",
            f"{API_ROOT}/repos/{self.repository}/releases",
            json.dumps(payload).encode("utf-8"),
        )
        assert isinstance(result, dict)
        return result

    def assets(self, release_id: int) -> list[dict[str, object]]:
        assets: list[dict[str, object]] = []
        page = 1
        while True:
            url = (
                f"{API_ROOT}/repos/{self.repository}/releases/{release_id}/assets"
                f"?per_page=100&page={page}"
            )
            result = self._request("GET", url)
            assert isinstance(result, list)
            assets.extend(item for item in result if isinstance(item, dict))
            if len(result) < 100:
                return assets
            page += 1

    def delete_asset(self, asset_id: int) -> None:
        self._request(
            "DELETE", f"{API_ROOT}/repos/{self.repository}/releases/assets/{asset_id}"
        )

    def upload_asset(self, release_id: int, path: Path) -> None:
        query = urllib.parse.urlencode({"name": path.name})
        url = (
            f"{UPLOAD_ROOT}/repos/{self.repository}/releases/{release_id}/assets?{query}"
        )
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._request("POST", url, path.read_bytes(), content_type)


def public_asset_sha256(asset: dict[str, object]) -> str | None:
    digest = asset.get("digest")
    if isinstance(digest, str) and digest.startswith("sha256:"):
        return digest.removeprefix("sha256:")
    url = asset.get("browser_download_url")
    if not isinstance(url, str):
        return None
    request = urllib.request.Request(url, headers={"User-Agent": "sat-heritage-archiver"})
    digest_object = hashlib.sha256()
    with urllib.request.urlopen(request) as response:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            digest_object.update(chunk)
    return digest_object.hexdigest()


def parse_renames(values: Iterable[str]) -> dict[str, str]:
    renames: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ArchiveError(f"rename must have the form SOURCE=ASSET: {value!r}")
        source, target = value.split("=", 1)
        if not source or not target or "/" in target or target in {".", ".."}:
            raise ArchiveError(f"invalid rename: {value!r}")
        if source in renames:
            raise ArchiveError(f"duplicate rename for {source!r}")
        renames[source] = target
    return renames


def mirror(
    year: str,
    sources: list[str],
    output_dir: Path,
    selected: set[str],
    renames: dict[str, str],
    output_format: str = "auto",
) -> tuple[list[Path], dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_records: list[dict[str, object]] = []
    discovered: dict[str, SolverArchive] = {}
    with tempfile.TemporaryDirectory(prefix=f"sat-competition-{year}-") as temp_dir:
        for number, source in enumerate(sources, start=1):
            source_path = Path(temp_dir) / f"source-{number}"
            record = download_source(source, source_path)
            archive = SolverArchive(source_path)
            roots = archive.roots()
            record["solvers"] = roots
            source_records.append(record)
            print(
                f"[OK] source {number}: {record['size']} bytes, "
                f"{len(roots)} solver(s)"
            )
            for root in roots:
                if root in discovered:
                    raise ArchiveError(f"solver {root!r} occurs in more than one source archive")
                discovered[root] = archive

        missing = sorted(selected.difference(discovered), key=str.casefold)
        if missing:
            raise ArchiveError("unknown solver(s): " + ", ".join(missing))
        names = sorted(selected or discovered.keys(), key=str.casefold)
        assets: list[Path] = []
        asset_records: list[dict[str, object]] = []
        used_asset_names: set[str] = set()
        for solver in names:
            asset_stem = renames.get(solver, solver)
            solver_format = discovered[solver].output_format(output_format)
            extension = ".zip" if solver_format == "zip" else ".tar.xz"
            asset_name = f"{asset_stem}{extension}"
            if asset_name in used_asset_names:
                raise ArchiveError(f"duplicate output asset name: {asset_name!r}")
            used_asset_names.add(asset_name)
            destination = output_dir / asset_name
            discovered[solver].write_solver(solver, destination, solver_format)
            digest = sha256_file(destination)
            assets.append(destination)
            asset_records.append(
                {
                    "solver": solver,
                    "asset": asset_name,
                    "archive_format": solver_format,
                    "size": destination.stat().st_size,
                    "sha256": digest,
                }
            )
            print(f"[OK] package {solver}: {asset_name} ({digest[:12]})")

    manifest: dict[str, object] = {
        "format": 1,
        "competition": year,
        "sources": source_records,
        "assets": asset_records,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return assets, manifest


def publish(
    assets: list[Path],
    manifest: dict[str, object],
    repository: str,
    tag: str,
    release_name: str,
    target: str | None,
    replace: bool,
    token: str,
) -> None:
    github = GitHubRelease(repository, token)
    release = github.release(tag)
    if release is None:
        source_lines = "\n".join(
            f"- {record['source']} (SHA-256 `{record['sha256']}`)"
            for record in manifest["sources"]  # type: ignore[index]
        )
        body = f"Mirror of the official SAT Competition {manifest['competition']} solver sources.\n\n{source_lines}"
        release = github.create_release(tag, release_name, body, target)
        print(f"[OK] release created: {tag}")
    release_id = int(release["id"])
    existing = {str(asset["name"]): asset for asset in github.assets(release_id)}
    for path in assets:
        current = existing.get(path.name)
        if current:
            local_digest = sha256_file(path)
            remote_digest = public_asset_sha256(current)
            if remote_digest == local_digest:
                print(f"[SKIP] upload {path.name}: identical asset already present")
                continue
            if not replace:
                raise GitHubError(
                    f"asset {path.name!r} already exists with different contents; "
                    "use --replace to overwrite it"
                )
            github.delete_asset(int(current["id"]))
            print(f"[OK] removed previous asset: {path.name}")
        github.upload_asset(release_id, path)
        print(f"[OK] uploaded: {path.name}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Split official competition archives into per-solver GitHub release assets."
    )
    result.add_argument("year", help="competition year, for example 2022")
    result.add_argument(
        "--archive",
        action="append",
        required=True,
        dest="archives",
        help="official ZIP/TAR URL or local path; repeat for multiple tracks",
    )
    result.add_argument(
        "--solver",
        action="append",
        default=[],
        help="only package this exact top-level solver directory; repeat as needed",
    )
    result.add_argument(
        "--rename",
        action="append",
        default=[],
        metavar="SOURCE=ASSET",
        help="rename an output asset while preserving the source directory",
    )
    result.add_argument("--output-dir", type=Path, help="default: dist/competition-sources/YEAR")
    result.add_argument(
        "--format",
        choices=("auto", "zip", "tar.xz"),
        default="auto",
        help="output format; auto (default) preserves ZIP competition distributions",
    )
    result.add_argument("--repo", default=DEFAULT_REPOSITORY, help="GitHub owner/repository")
    result.add_argument("--release-tag", help="default: YEAR-competition")
    result.add_argument("--release-name", help="default: SAT Competition YEAR sources")
    result.add_argument("--target", help="target branch or commit when creating the release")
    result.add_argument("--upload", action="store_true", help="create/update the GitHub release")
    result.add_argument(
        "--replace",
        action="store_true",
        help="replace an existing asset only when its checksum differs",
    )
    return result


def main(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    try:
        renames = parse_renames(args.rename)
        selected = set(args.solver)
        unknown_renames = sorted(set(renames).difference(selected)) if selected else []
        if unknown_renames:
            raise ArchiveError(
                "--rename source must also be selected with --solver: "
                + ", ".join(unknown_renames)
            )
        output_dir = args.output_dir or Path("dist") / "competition-sources" / args.year
        assets, manifest = mirror(
            args.year, args.archives, output_dir, selected, renames, args.format
        )
        if not args.upload:
            print(f"[PLAN] {len(assets)} asset(s) ready in {output_dir}; nothing uploaded")
            return 0
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise GitHubError("--upload requires GH_TOKEN or GITHUB_TOKEN")
        tag = args.release_tag or f"{args.year}-competition"
        release_name = args.release_name or f"SAT Competition {args.year} sources"
        publish(
            assets,
            manifest,
            args.repo,
            tag,
            release_name,
            args.target,
            args.replace,
            token,
        )
        return 0
    except (ArchiveError, GitHubError, OSError, urllib.error.URLError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
