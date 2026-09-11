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
from urllib.error import HTTPError
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

from satex_validation import (
    SATISFIABLE,
    UNSATISFIABLE,
    ValidationError,
    validate_drup_proof,
    validate_solver_run,
)

__version__ = "1.2.1-dev"

DOCKER_NS = "satex"
REGISTRY_URL = "https://github.com/sat-heritage/docker-images/releases/download/list/list.tgz"
NETWORK_TIMEOUT = 30
HOST_TIMEOUT_GRACE = 2

on_linux = platform.system() == "Linux"

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
        info(" ".join(cmd))
        subprocess.check_call(cmd)

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
    quiet = hasattr(args, "quiet") and args.quiet
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

def docker_uptodate_image(args, docker_argv, image):
    if image not in FROM_UPTODATE:
        argv = docker_argv + ["pull", image]
        info(" ".join(argv))
        subprocess.check_call(argv)
        FROM_UPTODATE.add(image)

def docker_build(args, docker_argv, tag, root, build_args=None, Dockerfile=None):
    build_args = build_args or {}
    with open(Dockerfile or os.path.join(root, "Dockerfile")) as fp:
        FROMs = [l.split()[1] for l in fp.readlines() \
                    if l.startswith("FROM") and "{" not in l]
        for f in FROMs:
            docker_uptodate_image(args, docker_argv, f)
    argv = docker_argv + ["build", "-t", tag, root]
    if args.no_cache:
        argv += ["--no-cache"]
    if Dockerfile:
        argv += ["-f", Dockerfile]
    for k,v in build_args.items():
        argv += ["--build-arg", f"{k}={v}"]
    info(" ".join(argv))
    subprocess.check_call(argv)

def build_images(args):
    docker_argv = check_docker()
    repo = Repository(args)

    bases_uptodate = set()

    only_dist_opts = ["RDEPENDS"]
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

        root = str(image.entry)

        build_args = {k: v.format(**image.vars) for k,v in setup.items() if \
                k not in hide_opts and isinstance(v, str)}
        build_args.update(image.vars)

        builder_path = setup["builder"]
        if not builder_path.startswith("generic/"):
            builder_path = os.path.join(image.entry, builder_path)
        builder_Dockerfile = os.path.join(builder_path, "Dockerfile")
        builder_target = f"{DOCKER_NS}/builder-{image.name}"

        if "builder_base" in setup:
            build_args["BUILDER_BASE"] = setup["builder_base"]
            docker_uptodate_image(args, docker_argv, setup["builder_base"])

        docker_build(args, docker_argv, builder_target, root,
                build_args=build_args, Dockerfile=builder_Dockerfile)

        base_version = setup["base_version"]
        base_root = os.path.join("base", base_version)
        base_from = setup.get("base_from")
        base_args = {}
        base_tag = base_version
        if base_from:
            base_args["BASE"] = base_from
            from_tag = base_from.replace("/","_").replace(":","-")
            base_tag = f"{base_version}-{from_tag}"
        base_target = f"{DOCKER_NS}/base:{base_tag}"
        if base_target not in bases_uptodate:
            docker_build(args, docker_argv, base_target, base_root, base_args)
            bases_uptodate.add(base_target)

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

            docker_build(args, docker_argv, f"{DOCKER_NS}/{image.name}",
                    root, dist_args, Dockerfile=dist_Dockerfile)
        finally:
            os.unlink(dbjson)


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

    info(f"Testing SAT with {sat_path}")
    info(f"Testing UNSAT with {unsat_path}")

    def call(test_name, image, image_args, cnf_path, expected_status):
        print(test_name, end="...", flush=True)
        ret, output = docker_runs(
            args,
            [image.name],
            docker_args=docker_args,
            image_args=image_args,
            capture_output=True,
        )
        msg = _retstr.get(ret, ret)
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
        return call("sat", image, [args.file], sat_path, SATISFIABLE)

    def test_gz(image):
        return call("sat-gz", image, [f"{args.file}.gz"], sat_gz_path, SATISFIABLE)

    def test_unsat(image):
        return call("unsat", image, [args.unsat_file], unsat_path, UNSATISFIABLE)

    def test_proof(image):
        if "argsproof" not in image.registry:
            return True
        proof_path = tests_dir / "proof.tmp"
        proof_path.unlink(missing_ok=True)
        try:
            if not call(
                "proof-result",
                image,
                [args.unsat_file, proof_path.name],
                unsat_path,
                UNSATISFIABLE,
            ):
                return False
            print("proof-check", end="...", flush=True)
            validate_drup_proof(unsat_path, proof_path)
            print(green("ok"))
            return True
        except (OSError, ValidationError, ValueError) as exc:
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
        info(f"Testing {image.name}")
        fails = [test.__name__[5:] for test in tests if not test(image)]
        if fails:
            failures.append((image, fails))

    if not failures:
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
    def brace_expand(s):
        """
        Bash-like brace+comma expansion
        Source: https://rosettacode.org/wiki/Brace_expansion
        """
        def getitem(s, depth=0):
            out = [""]
            while s:
                c = s[0]
                if depth and (c == ',' or c == '}'):
                    return out,s
                if c == '{':
                    x = getgroup(s[1:], depth+1)
                    if x:
                        out,s = [a+b for a in out for b in x[0]], x[1]
                        continue
                if c == '\\' and len(s) > 1:
                    s, c = s[1:], c + s[1]
                out, s = [a+c for a in out], s[1:]
            return out,s

        def getgroup(s, depth):
            out, comma = [], False
            while s:
                g,s = getitem(s, depth)
                if not s: break
                out += g
                if s[0] == '}':
                    if comma: return out, s[1:]
                    return ['{' + a + '}' for a in out], s[1:]
                if s[0] == ',':
                    comma,s = True, s[1:]
            return None
        return getitem(s)[0]

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
        p.set_defaults(func=build_images)

        p = subparsers.add_parser("test",
                help=f"Test {DOCKER_NS} Docker images",
                parents=[spec_parser, status_parser, run_parser, tracks_parser, docker_parser])
        p.add_argument("--quiet", "-q", action="store_true")
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
