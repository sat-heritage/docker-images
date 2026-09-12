#!/usr/bin/env python

# Homepage: https://github.com/sat-heritage/docker-images
# MIT License

import argparse
import fnmatch
import json
import glob
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import re
import tarfile
import tempfile
import textwrap
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from satex_validation import (
    SATISFIABLE,
    UNSATISFIABLE,
    ValidationError,
    read_dimacs,
    validate_drup_proof,
    validate_model,
    validate_solver_result,
    validate_solver_run,
)

__version__ = "1.2.1-dev"

DOCKER_NS = "satex"
REGISTRY_URL = "https://github.com/sat-heritage/docker-images/releases/download/list/list.tgz"
NETWORK_TIMEOUT = 30
HOST_TIMEOUT_GRACE = 2

BUILDER_STAGES = {
    "generic/2000": [
        ("build-environment", "buildenv"),
        ("source-extract", "source"),
        ("compile", "builder"),
    ],
    "generic/v1": [
        ("source-extract", "unpack"),
        ("build-environment", "buildenv"),
        ("compile", "builder"),
    ],
    "generic/starexec": [
        ("build-environment", "buildenv"),
        ("source-extract", "source"),
        ("compile", "builder"),
    ],
    "generic/binary-v1": [("source-extract", "source")],
    "generic/binary-tar": [("source-extract", "source")],
}

DIST_STAGES = {
    "v1": [
        ("runtime-dependencies", "runtime"),
        ("image-assemble", "image"),
    ],
}

on_linux = platform.system() == "Linux"


def brace_expand(s):
    """Perform the limited brace-and-comma expansion used by source URLs."""
    def getitem(value, depth=0):
        out = [""]
        while value:
            c = value[0]
            if depth and (c == ',' or c == '}'):
                return out, value
            if c == '{':
                group = getgroup(value[1:], depth + 1)
                if group:
                    out, value = [a + b for a in out for b in group[0]], group[1]
                    continue
            if c == '\\' and len(value) > 1:
                value, c = value[1:], c + value[1]
            out, value = [a + c for a in out], value[1:]
        return out, value

    def getgroup(value, depth):
        out, comma = [], False
        while value:
            group, value = getitem(value, depth)
            if not value:
                break
            out += group
            if value[0] == '}':
                if comma:
                    return out, value[1:]
                return ['{' + a + '}' for a in out], value[1:]
            if value[0] == ',':
                comma, value = True, value[1:]
        return None

    return getitem(s)[0]


def base_cache_tag(base_version, base_from=None, apt_snapshot=None):
    """Build a short Docker tag for a possibly digest-pinned base image."""
    tag = base_version
    if base_from:
        from_image, separator, from_digest = base_from.partition("@")
        from_tag = from_image.replace("/", "_").replace(":", "-")
        if separator:
            from_tag += "-" + from_digest.rsplit(":", 1)[-1][:12]
        tag += f"-{from_tag}"
    if apt_snapshot:
        tag += f"-snapshot-{apt_snapshot[:8]}"
    return tag


class BuildReporter:
    def __init__(self, args):
        self.terse = getattr(args, "terse", False)
        self.status_file = getattr(args, "status_file", None)
        if self.status_file:
            status_path = Path(self.status_file)
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text("", encoding="utf-8")

    def report(self, status, image, stage, detail=""):
        detail = str(detail).replace("\n", " ").strip()
        event = {
            "image": image,
            "stage": stage,
            "status": status,
        }
        if detail:
            event["detail"] = detail
        if self.status_file:
            with open(self.status_file, "a", encoding="utf-8") as fp:
                json.dump(event, fp, sort_keys=True)
                fp.write("\n")
        if self.terse:
            suffix = f" ({detail})" if detail else ""
            print(f"{status:<4} {image:<35} {stage}{suffix}", flush=True)


def source_urls(image):
    template = image.setup.get("download_url")
    if not isinstance(template, str) or not template:
        return []
    return brace_expand(template.format(**image.vars))


def probe_source_url(url, opener=urlopen):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https", "ftp"}:
        if not os.path.isfile(url):
            raise FileNotFoundError(url)
        return
    request = Request(
        url,
        headers={
            "Range": "bytes=0-0",
            "User-Agent": f"satex/{__version__}",
        },
    )
    with opener(request, timeout=NETWORK_TIMEOUT):
        pass


def source_error_detail(exc):
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, URLError):
        return str(exc.reason)
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, FileNotFoundError):
        return "local file not found"
    return str(exc)

def color(s, color, mode=1):
    return f"\033[{mode};{color}m{s}\033[0m"
def red(s):
    return color(s, 31)
def green(s):
    return color(s, 32)
def yellow(s):
    return color(s, 33)

def error(msg, exit=True):
    print("\033[1;31mERROR %s\033[0m" % msg, file=sys.stderr)
    if exit:
        sys.exit(1)

def warn(msg):
    print("\033[1;33m! %s\033[0m" % msg, file=sys.stderr)

def info(msg):
    print("\033[92m+ %s\033[0m" % msg, file=sys.stderr)

def in_repository():
    return os.path.isfile("index.json")

IN_REPOSITORY = in_repository()

##
#
# List of images

def fetch_registry(args, opener):
    with opener("index.json") as fp:
        index = json.load(fp)
    reg = {}
    cfg = {}
    for tag in sorted(index, key=lambda v: str(v)):
        with opener(f"{tag}/solvers.json") as fp:
            reg[tag] = json.load(fp)
        with opener(f"{tag}/setup.json") as fp:
            cfg[tag] = json.load(fp)
    return reg, cfg

if not IN_REPOSITORY:
    from appdirs import user_cache_dir
    cache_validity = 3600*4
    cache_dir = user_cache_dir("satex", "satex")
    cache_file = os.path.join(cache_dir, "list.tgz")

def is_cache_valid(args):
    if args.refresh_list:
        return False
    if not os.path.exists(cache_file):
        return False
    age = time.time() - os.path.getmtime(cache_file)
    if age > cache_validity:
        return False
    return True

def refresh_cache(args, force=False):
    if force or not is_cache_valid(args):
        os.makedirs(cache_dir, exist_ok=True)
        info(f"fetching {REGISTRY_URL}")
        with urlopen(REGISTRY_URL, timeout=NETWORK_TIMEOUT) as orig, \
                open(cache_file, "wb") as dest:
            shutil.copyfileobj(orig, dest, length=1024 * 1024)

def get_registry(args):
    if IN_REPOSITORY:
        return fetch_registry(args, open)
    else:
        refresh_cache(args)
        try:
            with tarfile.open(cache_file, "r") as tar:
                return fetch_registry(args, tar.extractfile)
        except tarfile.ReadError:
            refresh_cache(args, force=True)
            return get_registry(args)

def make_name(reg, cfg, entry, solver):
    pattern = cfg[entry].get("image_name", "{SOLVER}:{ENTRY}")
    return pattern.format(ENTRY=entry, SOLVER=solver)

def is_no_pattern(spec):
    return not set(spec).intersection("?[*")

re_image_name = re.compile(r"[a-z0-9][a-z0-9._-]*:[A-Za-z0-9_][A-Za-z0-9_.-]*")
def valid_name(name):
    return re_image_name.fullmatch(name) is not None

def normalize_status(status):
    status = status.lower()
    if status in {"ok", "unstable", "fixme"}:
        return status
    return "unstable"

class Repository(object):
    def __init__(self, args):
        self.registry, self.setup = get_registry(args)
        self.images = {}
        self.names = []

        select_all = not hasattr(args, "all") or args.all
        if hasattr(args, "pattern") and is_no_pattern(args.pattern):
            select_all = True
        select_fixme = select_all or hasattr(args, "fixme") and args.fixme
        select_unstable = select_all or hasattr(args, "unstable") and args.unstable
        select_stable = select_all or (not select_unstable and not select_fixme)

        select_tracks = set([args.track]) if hasattr(args, "track") and args.track else None

        for entry in self.registry:
            for solver in self.registry[entry]:
                name = make_name(self.registry, self.setup, entry, solver)
                if hasattr(args, "pattern") and \
                        not fnmatch.fnmatch(name, args.pattern):
                    continue
                status = normalize_status(
                    self.registry[entry][solver].get("status", "unknown")
                )
                if status == "ok":
                    if not select_stable:
                        continue
                elif status == "fixme":
                    if not select_fixme:
                        continue
                elif not select_unstable:
                    continue

                if not valid_name(name):
                    error(f"invalid image name: '{name}'")

                tracks = self.registry[entry][solver].get("tracks", [])
                if select_tracks and not select_tracks.intersection(tracks):
                    continue

                self.images[name] = {"entry": entry, "solver": solver}
                self.names.append(name)

class ImageManager(object):
    def __init__(self, name, repo):
        self.repo = repo
        self.name = name
        self.entry = repo.images[name]["entry"]
        self.solver = repo.images[name]["solver"]
        self.setup = repo.setup[self.entry].copy()
        self.setup.update(self.setup.get(self.solver, {}))
        self.registry = repo.registry[self.entry][self.solver]
        self.vars = {
            "SOLVER": self.solver,
            "SOLVER_NAME": self.solver_name,
        }
    @property
    def solver_name(self):
        return self.registry.get("name", self.name)
    @property
    def status(self):
        return normalize_status(self.registry.get("status", "unknown"))


def get_list(args):
    images = Repository(args).images
    if(len(images) == 0):
        sys.exit("No matching images!")
    return images

def print_list(args):
    for image in get_list(args):
        print(image)

_info_first = ["name", "version", "authors", "base_from"]
_info_last = ["download_url", "status", "comment", "comments"]
_info_ignore = {"call"}
_info_label = {
    "base_from": "Environment",
    "download_url": "Download URL",
    "gz": "Gzip input",
}
_info_nowrap = {"download_url"}
def print_info(args):
    repo = Repository(args)
    for name in repo.images:
        image = ImageManager(name, repo)

        ignore = _info_ignore.union(_info_first).union(_info_last)
        keys = _info_first \
            + [k for k in sorted(image.registry.keys()) if k not in ignore] \
            + _info_last

        key_width = 0
        info = []
        for key in keys:
            if key in image.setup:
                value = image.setup[key].format(**image.vars)
            elif key in image.registry:
                value = image.registry[key]
            else:
                continue
            name = _info_label.get(key, key.title())
            if key == "base_from":
                builder_base = image.setup.get("builder_base")
                if builder_base:
                    if builder_base == value:
                        value += " (same as build)"
                    else:
                        value += f" (build: {builder_base})"
            elif key in ["args", "argsproof"]:
                name = "Call"
                if key == "argsproof":
                    name += " (proof)"
                value = f"{image.registry['call']} {' '.join(map(str,value))}"
            else:
                if isinstance(value, list):
                    value = ", ".join(map(str, value))
                else:
                    value = str(value)
            key_width = max(len(name), key_width)
            info.append({"key": key, "name": name, "value": value})

        key_width += 2
        line_width = key_width + 70
        if image.status == "ok":
            color = 32
        elif image.status == "fixme":
            color = 31
        else:
            color = 33
        print(f"{DOCKER_NS}/\033[1;{color}m{image.name}\033[0m")
        print("-"*line_width)
        for d in info:
            name = f"{d['name']}: "
            if d["key"] in _info_nowrap:
                print("{0:{key_width}}{1}".format(name, d["value"],
                            key_width=key_width))
            else:
                for p in d["value"].splitlines():
                    for line in textwrap.wrap(p):
                        print("{0:{key_width}}{1}".format(name, line,
                            key_width=key_width))
                        name = ""
        print()

#
##

##
#
# Docker run

def check_cmd(argv):
    DEVNULL = subprocess.DEVNULL if hasattr(subprocess, "DEVNULL") \
                else open(os.devnull, 'w')
    try:
        result = subprocess.run(
            argv, stdout=DEVNULL, stderr=DEVNULL, close_fds=True, check=False
        )
        return result.returncode == 0
    except OSError:
        return False

def check_sudo():
    return check_cmd(["sudo", "docker", "version"])

def docker_call():
    direct_docker = ["docker"]
    sudo_docker = ["sudo", "docker"]
    if on_linux:
        import grp
        try:
            docker_grp = grp.getgrnam("docker")
            if docker_grp.gr_gid in os.getgroups():
                return direct_docker
        except KeyError:
            raise
        if not check_sudo():
            error("""'sudo' is not installed and you are not in the 'docker' group.
Either install sudo, or add your user to the docker group by doing
   su -c "usermod -aG docker $USER" """)
        return sudo_docker
    return direct_docker

def check_docker():
    if not check_cmd(["docker", "version"]):
        if not on_linux:
            error("""Docker not found.
If you are using Docker Toolbox, make sure you are running 'satex'
within the 'Docker quickstart Terminal'.""")
        else:
            error("Docker not found.")
    docker_argv = docker_call()
    #if not check_cmd(docker_argv + ["version"]):
    #    error("Error: cannot connect to Docker. Make sure it is running.")
    return docker_argv

def run_docker_process(cmd, run_args, timeout, docker_argv, container_id):
    """Run Docker with a host-side deadline for legacy images.

    Older published images do not enforce the TIMEOUT environment variable.
    Killing the Docker client alone would leave their container running, so an
    expired host deadline also explicitly kills the named container.
    """
    try:
        return subprocess.run(cmd, timeout=timeout, **run_args)
    except subprocess.TimeoutExpired as exc:
        subprocess.run(
            docker_argv + ["kill", container_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return subprocess.CompletedProcess(cmd, 124, stdout=output)

def prepare_image(args, docker_argv, image):
    if args.pull or\
            not subprocess.check_output(docker_argv + ["images", "-q", image]):
        cmd = docker_argv + ["pull", image]
        quiet = getattr(args, "quiet", False) or getattr(args, "terse", False)
        if not quiet:
            info(" ".join(cmd))
        run_args = {}
        if quiet:
            run_args = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        subprocess.check_call(cmd, **run_args)

def easy_volume(v):
    if ":" in v:
        orig, dest = v.split(":")
        if orig[0] != "/" and os.path.isdir(orig):
            orig = os.path.abspath(orig)
        v = f"{orig}:{dest}"
    return v

def get_docker_volumes(args):
    opts = getattr(args, "volume") or []
    return [easy_volume(opt).split(":") for opt in opts]

_docker_opts = []
def docker_runs(args, images, docker_args=(), image_args=(), capture_output=False):
    docker_argv = check_docker()
    container_id = f"satex{os.getpid()}"
    argv = ["run", "--name", container_id, "--rm"]
    if hasattr(args, "timeout"):
        argv += ["-e", f"TIMEOUT={args.timeout}"]
    quiet = getattr(args, "quiet", False) or getattr(args, "terse", False)
    for opt in _docker_opts:
        if getattr(args, opt) is not None:
            val = getattr(args, opt)
            if isinstance(val, list):
                for v in val:
                    if opt == "volume":
                        v = easy_volume(v)
                    argv += ["--%s"%opt, v]
            else:
                argv += ["--%s" % opt, val]
    argv += list(docker_args)
    image_argv = ["--mode", args.mode] if hasattr(args, "mode") and args.mode else []
    image_argv += list(image_args)
    run_args = {}
    if capture_output:
        run_args["stdout"] = subprocess.PIPE
        run_args["stderr"] = subprocess.STDOUT
        run_args["text"] = True
        run_args["encoding"] = "utf-8"
        run_args["errors"] = "replace"
    elif quiet:
        run_args["stdout"] = subprocess.DEVNULL
        run_args["stderr"] = subprocess.DEVNULL
    global stop
    stop = False
    for image in images:
        image = f"{DOCKER_NS}/{image}"
        prepare_image(args, docker_argv, image)
        cmd = docker_argv + argv + [image] + image_argv
        if args.pretend:
            print(" ".join(cmd))
        else:
            def killer(s,f):
                global stop
                stop = True
                warn("Killing solver...")
                subprocess.run(
                    docker_argv + ["kill", container_id],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            signal.signal(signal.SIGINT, killer)
            info(" ".join(cmd)) if not quiet else None
            host_timeout = None
            if hasattr(args, "timeout") and args.timeout > 0:
                host_timeout = args.timeout + HOST_TIMEOUT_GRACE
            result = run_docker_process(
                cmd, run_args, host_timeout, docker_argv, container_id
            )
            ret = result.returncode
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            if stop:
                sys.exit(1)
            if ret == 124:
                if args.fail_if_timeout and not capture_output:
                    raise subprocess.TimeoutExpired(image, args.timeout)
                elif not quiet:
                    warn(f"{image} timeout")
            else:
                if not capture_output and ret not in {0, 10, 20}:
                    if not quiet:
                        error(f"Solver failed with return code {ret}")
    if not args.pretend:
        if capture_output:
            return ret, result.stdout
        return ret

def run_images(args):
    # automatically detect volume
    paths = [Path(args.dimacs).resolve()]
    if args.proof:
        paths.append(Path(args.proof).resolve())
    root = paths[0].parent
    if args.proof:
        root = Path(os.path.commonpath(paths))
    docker_args = ["-v", f"{root.as_posix()}:/data"]
    image_args = [p.relative_to(root).as_posix() for p in paths]

    images = get_list(args)
    ret = docker_runs(args, images, docker_args, image_args)
    if ret is not None:
        sys.exit(ret)

def runraw_images(args):
    images = get_list(args)
    # automatically tries to detect filenames and make volumes
    volumes = [v[-1].rstrip("/") for v in get_docker_volumes(args)]
    volume = "/data"
    i = 1
    while volume in volumes:
        volume = f"/data{i}"
        i += 1
    paths = []
    docker_args = []
    def is_localfile(p):
        return os.path.exists(p) or p.startswith("./")
    for arg in args.args:
        if is_localfile(arg):
            path = Path(arg).resolve()
            if not os.path.isdir(arg):
                path = path.parent
            paths.append(path)
    if paths:
        root = Path(os.path.commonpath(paths))
        warn(f"Mounting {root} as {volume}")
        docker_args = ["-v", f"{root.as_posix()}:{volume}"]
    def update_path(path):
        if not is_localfile(path):
            return path
        r = Path(path).resolve().relative_to(root).as_posix()
        r = os.path.join(volume, r)
        warn(f"Argument '{path}' detected as a local path, it has been rewritten to {r}")
        return r
    image_args = ["--raw"] + [update_path(arg) for arg in args.args]
    ret = docker_runs(args, images, docker_args, image_args)
    if ret is not None:
        sys.exit(ret)

def run_shell(args):
    images = get_list(args)
    assert args.image in images, "Unknown image"
    docker_runs(args, [args.image], ("-it", "--entrypoint", "bash"))

def safe_tar_members(tar, output_dir):
    """Yield only regular archive entries that remain below output_dir."""
    root = Path(output_dir).resolve()
    for member in tar:
        target = (root / member.name).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise tarfile.FilterError(
                f"archive member escapes destination: {member.name}"
            ) from exc
        if member.isdev() or member.isfifo():
            raise tarfile.FilterError(
                f"archive contains special file: {member.name}"
            )
        if member.issym() or member.islnk():
            raise tarfile.FilterError(
                f"archive contains unsupported link: {member.name}"
            )
        yield member

def extract(args):
    images = get_list(args)
    docker_argv = check_docker()
    os.makedirs(args.output_dir, exist_ok=True)
    for imageid in images:
        dest_dir = os.path.join(args.output_dir, imageid.replace(":","-"))
        if os.path.exists(dest_dir):
            print(f"Warning: destination '{dest_dir}' already exists.")
            print(f"CTRL+C to abort; ENTER to DELETE '{dest_dir}'")
            input()
            shutil.rmtree(dest_dir)
        image = f"{DOCKER_NS}/{imageid}"
        info(image)
        prepare_image(args, docker_argv, image)
        argv = docker_argv + ["run", "--rm", "-w", "/", "--entrypoint", "tar",
                image,  "-c", "solvers"]
        info(" ".join(argv))
        with subprocess.Popen(argv, stdout=subprocess.PIPE,
                stderr=sys.stderr) as p:
            with tarfile.open(mode="r|", fileobj=p.stdout) as t:
                if hasattr(tarfile, "data_filter"):
                    t.extractall(args.output_dir, filter="data")
                else:
                    t.extractall(
                        args.output_dir,
                        members=safe_tar_members(t, args.output_dir),
                    )
            if p.wait() != 0:
                raise subprocess.CalledProcessError(p.returncode, argv)
        os.rename(os.path.join(args.output_dir, "solvers"), dest_dir)

#
##

##
#
# repository management

FROM_UPTODATE = set()

def diagnostic_subprocess_args(args):
    if getattr(args, "terse", False):
        return {"stdout": sys.stderr, "stderr": sys.stderr}
    return {}


def docker_uptodate_image(args, docker_argv, image):
    if image not in FROM_UPTODATE:
        argv = docker_argv + ["pull", image]
        info(" ".join(argv))
        subprocess.check_call(argv, **diagnostic_subprocess_args(args))
        FROM_UPTODATE.add(image)


def dockerfile_base_images(root, Dockerfile=None):
    images = []
    aliases = set()
    with open(Dockerfile or os.path.join(root, "Dockerfile")) as fp:
        for line in fp:
            if not line.startswith("FROM"):
                continue
            fields = line.split()
            image = fields[1]
            if "{" not in image and image not in aliases:
                images.append(image)
            if len(fields) >= 4 and fields[-2].lower() == "as":
                aliases.add(fields[-1])
    return images


def docker_prepare_base_images(args, docker_argv, root, Dockerfile=None):
    for image in dockerfile_base_images(root, Dockerfile):
        docker_uptodate_image(args, docker_argv, image)


def docker_build(
    args,
    docker_argv,
    tag,
    root,
    build_args=None,
    Dockerfile=None,
    target=None,
):
    build_args = build_args or {}
    docker_prepare_base_images(args, docker_argv, root, Dockerfile)
    argv = docker_argv + ["build", "-t", tag, root]
    if args.no_cache:
        argv += ["--no-cache"]
    if Dockerfile:
        argv += ["-f", Dockerfile]
    if target:
        argv += ["--target", target]
    for k,v in build_args.items():
        argv += ["--build-arg", f"{k}={v}"]
    info(" ".join(argv))
    subprocess.check_call(argv, **diagnostic_subprocess_args(args))

def build_images(args):
    repo = Repository(args)
    reporter = BuildReporter(args)

    try:
        docker_argv = check_docker()
    except SystemExit:
        for name in repo.images:
            reporter.report("fail", name, "docker-engine", "unavailable")
        raise
    for name in repo.images:
        reporter.report("ok", name, "docker-engine")

    bases_uptodate = set()

    only_dist_opts = ["RDEPENDS", "APT_SNAPSHOT", "APT_CODENAME"]
    hide_opts = [
        "base_version",
        "base_from",
        "builder",
        "builder_base",
        "image_name",
    ]

    for name in repo.images:
        image = ImageManager(name, repo)
        setup = image.setup
        stage_image_tags = []

        def failure_detail(exc):
            if isinstance(
                exc,
                (HTTPError, URLError, TimeoutError, FileNotFoundError),
            ):
                return source_error_detail(exc)
            if isinstance(exc, subprocess.CalledProcessError):
                return f"exit {exc.returncode}"
            return str(exc) or exc.__class__.__name__

        def run_stage(stage, action, detail=""):
            reporter.report("run", image.name, stage, detail)
            try:
                action()
            except Exception as exc:
                reporter.report("fail", image.name, stage, failure_detail(exc))
                raise
            reporter.report("ok", image.name, stage)

        root = str(image.entry)

        build_args = {k: v.format(**image.vars) for k,v in setup.items() if \
                k not in hide_opts and isinstance(v, str)}
        build_args.update(image.vars)

        builder_path = setup["builder"]
        if not builder_path.startswith("generic/"):
            builder_path = os.path.join(image.entry, builder_path)
        builder_Dockerfile = os.path.join(builder_path, "Dockerfile")
        builder_target = f"{DOCKER_NS}/builder-{image.name}"

        try:
            urls = source_urls(image)
            if urls:
                def probe_sources():
                    for url in urls:
                        probe_source_url(url)
                run_stage("source-download", probe_sources)
            else:
                reporter.report("skip", image.name, "source-download", "no URL")

            if "builder_base" in setup:
                build_args["BUILDER_BASE"] = setup["builder_base"]

            def prepare_builder_images():
                if "builder_base" in setup:
                    docker_uptodate_image(
                        args, docker_argv, setup["builder_base"]
                    )
                docker_prepare_base_images(
                    args, docker_argv, root, builder_Dockerfile
                )

            run_stage("builder-base-image", prepare_builder_images)

            builder_stages = BUILDER_STAGES.get(setup["builder"])
            if builder_stages:
                for index, (stage, target) in enumerate(builder_stages):
                    last_stage = index == len(builder_stages) - 1
                    stage_tag = builder_target if last_stage else (
                        f"{DOCKER_NS}/stage-{stage}-{image.name}"
                    )
                    if not last_stage:
                        stage_image_tags.append(stage_tag)
                    run_stage(
                        stage,
                        lambda stage_tag=stage_tag, target=target: docker_build(
                            args,
                            docker_argv,
                            stage_tag,
                            root,
                            build_args=build_args,
                            Dockerfile=builder_Dockerfile,
                            target=target,
                        ),
                    )
                if not any(stage == "compile" for stage, _ in builder_stages):
                    reporter.report(
                        "skip", image.name, "compile", "binary distribution"
                    )
            else:
                run_stage(
                    "builder-build",
                    lambda: docker_build(
                        args,
                        docker_argv,
                        builder_target,
                        root,
                        build_args=build_args,
                        Dockerfile=builder_Dockerfile,
                    ),
                    "custom builder",
                )

            base_version = setup["base_version"]
            base_root = os.path.join("base", base_version)
            base_from = setup.get("base_from")
            base_args = {}
            if base_from:
                base_args["BASE"] = base_from
            apt_snapshot = setup.get("APT_SNAPSHOT")
            if apt_snapshot:
                base_args["APT_SNAPSHOT"] = apt_snapshot
                base_args["APT_CODENAME"] = setup["APT_CODENAME"]
            base_tag = base_cache_tag(base_version, base_from, apt_snapshot)
            base_target = f"{DOCKER_NS}/base:{base_tag}"
            if base_target not in bases_uptodate:
                def prepare_runtime_images():
                    if base_from:
                        docker_uptodate_image(args, docker_argv, base_from)
                    docker_prepare_base_images(args, docker_argv, base_root)

                run_stage("runtime-base-image", prepare_runtime_images)
                run_stage(
                    "runtime-base",
                    lambda: docker_build(
                        args,
                        docker_argv,
                        base_target,
                        base_root,
                        base_args,
                    ),
                )
                bases_uptodate.add(base_target)
            else:
                reporter.report(
                    "skip", image.name, "runtime-base", "already built"
                )

            dist_version = setup.get("dist_version", "v1")
            dist_Dockerfile = f"generic/dist-{dist_version}/Dockerfile"
            dist_args = {
                "BASE": base_target,
                "BUILDER_BASE": builder_target,
                "IMAGE_NAME": image.name,
                "SOLVER": build_args["SOLVER"],
                "SOLVER_NAME": build_args["SOLVER_NAME"],
            }
            for k in only_dist_opts:
                if k in setup:
                    dist_args[k] = setup[k]

            fd, dbjson = tempfile.mkstemp(".json", "file", root)
            try:
                fp = os.fdopen(fd, "w")
                json.dump({image.solver: image.registry}, fp)
                fp.close()
                dist_args["dbjson"] = os.path.basename(dbjson)

                dist_stages = DIST_STAGES.get(dist_version)
                if dist_stages:
                    for index, (stage, target) in enumerate(dist_stages):
                        last_stage = index == len(dist_stages) - 1
                        stage_tag = f"{DOCKER_NS}/{image.name}" if last_stage else (
                            f"{DOCKER_NS}/stage-{stage}-{image.name}"
                        )
                        if not last_stage:
                            stage_image_tags.append(stage_tag)
                        run_stage(
                            stage,
                            lambda stage_tag=stage_tag, target=target: docker_build(
                                args,
                                docker_argv,
                                stage_tag,
                                root,
                                dist_args,
                                Dockerfile=dist_Dockerfile,
                                target=target,
                            ),
                        )
                else:
                    run_stage(
                        "image-assemble",
                        lambda: docker_build(
                            args,
                            docker_argv,
                            f"{DOCKER_NS}/{image.name}",
                            root,
                            dist_args,
                            Dockerfile=dist_Dockerfile,
                        ),
                    )
            finally:
                os.unlink(dbjson)
        finally:
            for stage_tag in stage_image_tags:
                subprocess.run(
                    docker_argv + ["image", "rm", "-f", stage_tag],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )


_retstr = {
    10: "SAT",
    20: "UNSAT",
    124: "TIMEOUT",
}

def test_images(args):
    with tempfile.TemporaryDirectory(prefix="satex-tests-") as workspace:
        return test_images_in_workspace(args, Path(workspace))

def test_images_in_workspace(args, tests_dir):
    source_tests_dir = Path("tests").resolve()
    filenames = [args.file, f"{args.file}.gz", args.unsat_file]
    for filename in filenames:
        source = source_tests_dir / filename
        if not source.is_file():
            error(f"missing test instance: {source}")
        shutil.copy2(source, tests_dir / filename)

    docker_args = ["-v", f"{tests_dir}:/data"]
    sat_path = tests_dir / args.file
    sat_gz_path = tests_dir / f"{args.file}.gz"
    unsat_path = tests_dir / args.unsat_file

    if not args.terse:
        info(f"Testing SAT with {sat_path}")
        info(f"Testing UNSAT with {unsat_path}")

    def report(status, image, test_name, detail=""):
        suffix = f" ({detail})" if detail else ""
        print(f"{status:<4} {image.name} {test_name}{suffix}", flush=True)

    def call(
        test_name,
        image,
        image_args,
        cnf_path,
        expected_status,
        report_launch=False,
    ):
        if not args.terse:
            print(test_name, end="...", flush=True)
        ret, output = docker_runs(
            args,
            [image.name],
            docker_args=docker_args,
            image_args=image_args,
            capture_output=True,
        )
        msg = _retstr.get(ret, ret)
        if args.terse:
            launched = ret not in {125, 126, 127}
            if report_launch:
                report(
                    "ok" if launched else "fail",
                    image,
                    "launch",
                    "" if launched else msg,
                )
            if not launched:
                report("skip", image, f"{test_name}-termination", "launch failed")
                report("skip", image, f"{test_name}-result", "launch failed")
                if expected_status == SATISFIABLE:
                    report("skip", image, f"{test_name}-model", "launch failed")
                return False

            terminated = ret != 124
            report(
                "ok" if terminated else "fail",
                image,
                f"{test_name}-termination",
                msg,
            )
            if not terminated:
                report("skip", image, f"{test_name}-result", "timeout")
                if expected_status == SATISFIABLE:
                    report("skip", image, f"{test_name}-model", "timeout")
                return False

            try:
                model = validate_solver_result(expected_status, ret, output)
            except (ValidationError, ValueError) as exc:
                report("fail", image, f"{test_name}-result", str(exc))
                if expected_status == SATISFIABLE:
                    report("skip", image, f"{test_name}-model", "invalid result")
                return False

            report("ok", image, f"{test_name}-result", msg)
            if expected_status == SATISFIABLE:
                try:
                    variables, clauses = read_dimacs(cnf_path)
                    validate_model(variables, clauses, model)
                except (OSError, ValidationError, ValueError) as exc:
                    report("fail", image, f"{test_name}-model", str(exc))
                    return False
                report("ok", image, f"{test_name}-model")
            return True

        try:
            validate_solver_run(cnf_path, expected_status, ret, output)
        except (OSError, ValidationError, ValueError) as exc:
            print(red("fail"), f"({msg}: {exc})")
            if output and not args.quiet:
                print(output, end="" if output.endswith("\n") else "\n")
            return False
        else:
            print(green("ok"), f"({msg})")
            return True

    def test_cnf(image):
        return call(
            "sat", image, [args.file], sat_path, SATISFIABLE, report_launch=True
        )

    def test_gz(image):
        return call(
            "sat-gzip",
            image,
            [f"{args.file}.gz"],
            sat_gz_path,
            SATISFIABLE,
        )

    def test_unsat(image):
        return call("unsat", image, [args.unsat_file], unsat_path, UNSATISFIABLE)

    def test_proof(image):
        if "argsproof" not in image.registry:
            if args.terse:
                report("skip", image, "unsat-proof", "unsupported")
            return True
        proof_path = tests_dir / "proof.tmp"
        proof_path.unlink(missing_ok=True)
        try:
            if not call(
                "unsat-proof-run",
                image,
                [args.unsat_file, proof_path.name],
                unsat_path,
                UNSATISFIABLE,
            ):
                return False
            if not args.terse:
                print("proof-check", end="...", flush=True)
            validate_drup_proof(unsat_path, proof_path)
            if args.terse:
                report("ok", image, "unsat-proof")
            else:
                print(green("ok"))
            return True
        except (OSError, ValidationError, ValueError) as exc:
            if args.terse:
                report("fail", image, "unsat-proof", str(exc))
            else:
                print(red("fail"), f"({exc})")
            return False
        finally:
            proof_path.unlink(missing_ok=True)

    def test_modes(image):
        ok = True
        for mode in [k for k in image.registry if k.startswith("args")]:
            mode = mode[4:]
            if not mode or mode == "proof":
                continue
            image_args = ["--mode", mode, f"{args.file}.gz"]
            ok = call(
                f"mode-{mode}", image, image_args, sat_gz_path, SATISFIABLE
            ) and ok
        return ok

    tests = [test_cnf, test_gz, test_unsat, test_proof, test_modes]

    failures = []

    repo = Repository(args)
    docker_argv = check_docker()
    for name in repo.images:
        prepare_image(args, docker_argv, f"{DOCKER_NS}/{name}")
    for name in repo.images:
        image = ImageManager(name, repo)
        if not args.terse:
            info(f"Testing {image.name}")
        fails = [test.__name__[5:] for test in tests if not test(image)]
        if fails:
            failures.append((image, fails))

    if args.terse:
        pass
    elif not failures:
        print(green("Bravo :-)"))
    else:
        print(red("Failed tests:"))
        for image, fails in failures:
            print(f"{image.name} failed tests {' '.join(fails)}")

    if failures:
        sys.exit(1)

def push_images(args):
    docker_argv = check_docker()
    for image in get_list(args):
        argv = docker_argv + ["push", f"{DOCKER_NS}/{image}"]
        info(" ".join(argv))
        subprocess.check_call(argv)

def mrproper(args):
    docker_argv = check_docker()
    output = subprocess.check_output(docker_argv + ["images", "-f",
                                    f"reference={DOCKER_NS}/*",
                                    "--format", "{{.Repository}}:{{.Tag}}"])
    todel = [l.strip() for l in output.decode().split("\n") if l]
    if args.pattern:
        todel = fnmatch.filter(todel, f"{DOCKER_NS}/{args.pattern}")
    if not todel:
        return
    todel.sort()
    argv = docker_argv + ["rmi"] + list(todel)
    if args.pretend:
        print(" ".join(argv))
    else:
        info(" ".join(argv))
        sys.exit(subprocess.call(argv))

def dependencies(args):
    docker_argv = check_docker()
    repo = Repository(args)
    deps = set()
    for name in repo.images:
        image = ImageManager(name, repo)
        setup = image.setup
        if "builder_base" in setup:
            deps.add(setup["builder_base"])
        deps.add(setup["base_from"])
    for image in deps:
        print(image)
        if args.pull:
            prepare_image(args, docker_argv, image)

def download_src(args):
    os.makedirs(args.output_dir, exist_ok=True)
    repo = Repository(args)
    for name in repo.images:
        image = ImageManager(name, repo)
        setup = image.setup
        src_urls = setup["download_url"].format(**image.vars)
        src_urls = brace_expand(src_urls)
        for src_url in src_urls:
            if args.subdir_entry:
                os.makedirs(os.path.join(args.output_dir, str(image.entry)), exist_ok=True)
            try:
                with urlopen(src_url, timeout=NETWORK_TIMEOUT) as fp:
                    filename = fp.headers.get_filename()
                    if not filename:
                        filename = unquote(os.path.basename(urlparse(src_url).path))
                    filename = os.path.basename(filename)
                    if not filename or filename in {".", ".."}:
                        raise ValueError("download URL does not provide a safe filename")

                    if args.subdir_entry:
                        filename = os.path.join(str(image.entry), filename)
                    filename = os.path.join(args.output_dir, filename)
                    if os.path.exists(filename) and not args.overwrite:
                        error(f"{image.name}: {filename} already exists. Use --overwrite option to overwrite it")
                    print(f"{image.name}: downloading to {filename}...", end="", flush=True)
                    with open(filename, "wb") as dest:
                        shutil.copyfileobj(fp, dest, length=1024 * 1024)
                    print(green("ok"))
                    if "zenodo.org" in src_url:
                        time.sleep(0.5)

            except HTTPError as e:
                error(f"{image.name}: error while downloading {src_url} ({e})",
                        exit=False)

            except Exception as e:
                error(f"{image.name}: error while downloading {src_url} ({type(e)} {e})",
                        exit=False)


def print_version(args):
    print(__version__)
#
##

def main(redirected=False):

    if IN_REPOSITORY and not redirected and \
            os.path.abspath(__file__) != os.path.abspath("satex.py"):
        info(f"using {os.path.abspath('satex.py')}")
        del sys.modules["satex"]
        sys.path.insert(0, os.getcwd())
        from satex import main
        return main(redirected=True)

    parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]),
            description="Helper script for managing SAT Heritage Docker images",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=textwrap.dedent(f"""\
            GitHub:    https://github.com/sat-heritage/docker-images
            DockerHub: https://hub.docker.com/u/satex
            Version:   {__version__}"""))

    parser.add_argument("--refresh-list", default=False, action="store_true",
            help="Force refresh of the list of images")
    parser.add_argument("--pretend", "-p", default=False, action="store_true",
            help="Print Docker commands without executing them")

    subparsers = parser.add_subparsers(help="commands")

    ##
    # options shared by several sub-commands
    #
    status_parser = argparse.ArgumentParser(add_help=False)
    status_parser.add_argument("--unstable", action="store_true",
            help="Consider images with non-ok and non-FIXME status")
    status_parser.add_argument("--fixme", action="store_true",
            help="Consider images with FIXME status")
    status_parser.add_argument("--all", "-a", action="store_true",
            help="Consider all images, with any status")

    spec_parser = argparse.ArgumentParser(add_help=False)
    spec_parser.add_argument("pattern",
            help="Pattern for filtering images")

    tracks_parser = argparse.ArgumentParser(add_help=False)
    tracks_parser.add_argument("--track",
            help="Filter solvers from the given track")

    docker_parser = argparse.ArgumentParser(add_help=False)
    docker_parser.add_argument("--pull", action="store_true",
            help="Explicitly pull the image")
    docker_parser.add_argument("-v", "--volume", action="append",
            help="(Docker option) Mount a volume")
    _docker_opts.append("volume")
    docker_parser.add_argument("-e", "--env", action="append",
            help="(Docker option) Set environment variables")
    _docker_opts.append("env")

    run_parser = argparse.ArgumentParser(add_help=False)
    run_parser.add_argument("--timeout", type=int, default=3600,
            help="Timeout for solver (in seconds; default: 3600)")
    run_parser.add_argument("--fail-if-timeout", action="store_true",
            help="Fail if timeout occurs")
    #
    ##

    ##
    # sub-commands
    #

    p = subparsers.add_parser("list",
            help=f"List {DOCKER_NS} Docker images",
            parents=[status_parser, tracks_parser])
    p.add_argument("pattern", default="*", nargs="?",
            help="Pattern for filtering images (default: *)")
    p.set_defaults(func=print_list)

    p = subparsers.add_parser("info",
            help=f"Display information about the solver embedded in the given Docker images",
            parents=[spec_parser, tracks_parser])
    p.set_defaults(func=print_info)

    p = subparsers.add_parser("run",
            help=f"Run one or several {DOCKER_NS} Docker images",
            parents=[spec_parser, status_parser, tracks_parser,
                run_parser, docker_parser])
    p.add_argument("--mode",
            help="Select args mode")
    p.add_argument("dimacs",
            help="DIMACS file (possibly gzipped)")
    p.add_argument("proof", nargs="?",
            help="Output file for proof")
    p.set_defaults(func=run_images)

    p = subparsers.add_parser("run-raw",
            help=f"Run one or several {DOCKER_NS} Docker images with direct call to solvers",
            parents=[spec_parser, status_parser, tracks_parser,
                run_parser, docker_parser])
    p.add_argument("args", nargs=argparse.REMAINDER,
            help="Arguments to docker image")
    p.set_defaults(func=runraw_images)

    p = subparsers.add_parser("shell",
            help=f"Open shell within the given {DOCKER_NS} Docker image",
            parents=[docker_parser])
    p.add_argument("image", help="{DOCKER_NS} image")
    p.set_defaults(func=run_shell)

    p = subparsers.add_parser("extract",
            help=f"Extract solvers binaries from {DOCKER_NS} Docker images",
            parents=[spec_parser, status_parser, tracks_parser, docker_parser])
    p.add_argument("output_dir", help="Output directory")
    p.set_defaults(func=extract)

    p = subparsers.add_parser("mrproper",
            help=f"Remove all {DOCKER_NS} Docker images")
    p.add_argument("pattern", default=None, nargs="?",
            help="Pattern for filtering images")
    p.set_defaults(func=mrproper)

    if IN_REPOSITORY:
        p = subparsers.add_parser("build",
                help=f"Build {DOCKER_NS} Docker images",
                parents=[spec_parser, status_parser, tracks_parser])
        p.add_argument("--no-cache", action="store_true",
                help="docker build option")
        p.add_argument("--terse", action="store_true",
                help="Print one concise status line for each build stage")
        p.add_argument("--status-file",
                help="Write build stage events as JSON Lines")
        p.set_defaults(func=build_images)

        p = subparsers.add_parser("test",
                help=f"Test {DOCKER_NS} Docker images",
                parents=[spec_parser, status_parser, run_parser, tracks_parser, docker_parser])
        p.add_argument("--quiet", "-q", action="store_true")
        p.add_argument("--terse", action="store_true",
                help="Print one concise status line for each validation stage")
        p.add_argument("--file", "-f", default="aim-200-1_6-yes1-1.cnf",
                help=".cnf test file (should also exists with .gz)")
        p.add_argument("--unsat-file", default="simple-unsat.cnf",
                help="UNSAT .cnf test file (default: simple-unsat.cnf)")
        p.set_defaults(func=test_images, timeout=10, fail_if_timeout=True)

        p = subparsers.add_parser("push",
                help=f"Push {DOCKER_NS} Docker images",
                parents=[spec_parser, status_parser, tracks_parser])
        p.set_defaults(func=push_images)

        p = subparsers.add_parser("image-deps",
                help=f"List Docker image dependencies")
        p.add_argument("--pull", action="store_true",
                help="pull images")
        p.set_defaults(func=dependencies)

        p = subparsers.add_parser("fetch-sources",
                help=f"Fetch solver sources",
                parents=[spec_parser])
        p.add_argument("output_dir", help="Output directory")
        p.add_argument("--overwrite", help="Allow writing over existing files",
                action="store_true", default=False)
        p.add_argument("--subdir-entry", help="Output in sub-directory named as the entry (year)",
                action="store_true", default=False)
        p.set_defaults(func=download_src)


    subparsers.add_parser("version",
                help="Print script version")\
        .set_defaults(func=print_version)

    #
    ##

    args = parser.parse_args()
    if not hasattr(args, "func"):
        return parser.print_help()
    return args.func(args)

if __name__ == "__main__":
    main()
