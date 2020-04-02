#!/usr/bin/env python

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
import tarfile
import tempfile
import textwrap
import time
from urllib.request import urlopen

__version__ = "0.99-dev"

DOCKER_NS = "satex"
REGISTRY_URL = "https://github.com/sat-heritage/docker-images/releases/download/list/list.tgz"

on_linux = platform.system() == "Linux"

def error(msg):
    print(msg, file=sys.stderr)
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
        with urlopen(REGISTRY_URL) as orig, \
                open(cache_file, "wb") as dest:
            dest.write(orig.read())

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
                status = self.registry[entry][solver].get("status", "unknown")
                if status == "ok":
                    if not select_stable:
                        continue
                elif status.startswith("FIXME"):
                    if not select_fixme:
                        continue
                elif not select_unstable:
                    continue

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
        return self.registry["name"]
    @property
    def status(self):
        return self.registry.get("status", "unknown")


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
        elif image.status.startswith("FIXME"):
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
        subprocess.call(argv, stdout=DEVNULL, stderr=DEVNULL, close_fds=True)
        return True
    except:
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
            error("""Error: 'sudo' is not installed and you are not in the 'docker' group.
Either install sudo, or add your user to the docker group by doing
   su -c "usermod -aG docker $USER" """)
        return sudo_docker
    return direct_docker

def check_docker():
    if not check_cmd(["docker", "version"]):
        if not on_linux:
            error("""Error: Docker not found.
If you are using Docker Toolbox, make sure you are running 'satex'
within the 'Docker quickstart Terminal'.""")
        else:
            error("Error: Docker not found.")
    docker_argv = docker_call()
    #if not check_cmd(docker_argv + ["version"]):
    #    error("Error: cannot connect to Docker. Make sure it is running.")
    return docker_argv

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

_docker_opts = []
def docker_runs(args, images, docker_args=(), image_args=()):
    docker_argv = check_docker()
    container_id = f"satex{os.getpid()}"
    argv = ["run", "--name", container_id, "--rm"]
    if hasattr(args, "timeout"):
        argv += ["-e", f"TIMEOUT={args.timeout}"]
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
    for image in images:
        image = f"{DOCKER_NS}/{image}"
        prepare_image(args, docker_argv, image)
        cmd = docker_argv + argv + [image] + image_argv
        if args.pretend:
            print(" ".join(cmd))
        else:
            def killer(s,f):
                warn("Killing solver...")
                argv = docker_argv + ["kill", container_id]
                subprocess.run(argv, stdout=subprocess.DEVNULL)
            signal.signal(signal.SIGINT, killer)
            info(" ".join(cmd))
            ret = subprocess.run(cmd).returncode
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            if ret == 124:
                if args.fail_if_timeout:
                    raise subprocess.TimeoutExpired(image, args.timeout)
                else:
                    warn(f"{image} timeout")
            else:
                assert ret == 0 or 10 <= ret <= 20, f"Solver failed! ({ret})"
    if not args.pretend:
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
    ret = docker_runs(args, images, image_args=["--raw"]+args.args)
    if ret is not None:
        sys.exit(ret)

def run_shell(args):
    images = get_list(args)
    assert args.image in images, "Unknown image"
    docker_runs(args, [args.image], ("-it", "--entrypoint", "bash"))

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
                t.extractall(args.output_dir)
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

def docker_build(args, docker_argv, tag, root, build_args={}, Dockerfile=None):
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


def test_images(args):
    images = get_list(args)
    docker_args = ["-v", f"{os.path.abspath('tests')}:/data"]
    dimacs = args.cnf
    info(f"Testing {dimacs}")
    dimacs = os.path.basename(dimacs)
    docker_runs(args, images, docker_args, image_args=(dimacs,))

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
        p.add_argument("--mode",
            help="Select args mode")
        p.add_argument("--cnf", "-f", default="tests/cmu-bmc-barrel6.cnf.gz")
        p.set_defaults(func=test_images)

        p = subparsers.add_parser("push",
                help=f"Push {DOCKER_NS} Docker images",
                parents=[spec_parser, status_parser, tracks_parser])
        p.set_defaults(func=push_images)

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
