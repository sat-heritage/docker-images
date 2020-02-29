#!/usr/bin/env python

from appdirs import user_cache_dir
import argparse
import fnmatch
import json
import glob
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

DOCKER_NS = "satex"
REGISTRY_BASEURL = "https://raw.githubusercontent.com/sat-heritage/docker-images/master/"

cache_validity = 3600*4
cache_dir = user_cache_dir("satex", "satex")
cache_file = os.path.join(cache_dir, "images.json")

on_linux = platform.system() == "Linux"

def error(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)

def info(msg):
    print("\033[92m+ %s\033[0m" % msg, file=sys.stderr)

def in_repository():
    return os.path.isfile("index.json")

IN_REPOSITORY = in_repository()

##
#
# List of images
def make_name(reg, cfg, entry, solver):
    pattern = cfg[entry].get("image_name", "{SOLVER}:{ENTRY}")
    return pattern.format(ENTRY=entry, SOLVER=solver)

def images_of_registry(reg, cfg):
    return [make_name(reg, cfg, entry, solver) \
                for entry in reg for solver in reg[entry]]

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

def fetch_list(args, opener):
    reg, cfg = fetch_registry(args, opener)
    return images_of_registry(reg, cfg)

def get_local_list(args):
    return fetch_list(args, open)

def cache_get(args):
    if args.refresh_list:
        return
    if not os.path.exists(cache_file):
        return
    age = time.time() - os.path.getmtime(cache_file)
    if age > cache_validity:
        return
    info(f"using cache {cache_file}")
    with open(cache_file) as fp:
        return json.load(fp)

def cache_list(images):
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    with open(cache_file, "w") as fp:
        json.dump(images, fp)

def get_dist_list(args):
    images = cache_get(args)
    if images:
        return images
    def uopen(name):
        info(f"fetching {name}")
        return urlopen(f"{REGISTRY_BASEURL}{name}")
    images = fetch_list(args, uopen)
    cache_list(images)
    return images

def get_list(args):
    if IN_REPOSITORY:
        images = get_local_list(args)
    else:
        images = get_dist_list(args)
    if hasattr(args, "pattern"):
        images = fnmatch.filter(images, args.pattern)
    assert len(images), "No matching images!"
    return images

def print_list(args):
    for image in get_list(args):
        print(image)

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
If you are using Docker Toolbox, make sure you are running 'colomoto-docker'
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

def docker_runs(args, images, docker_args=(), image_args=()):
    docker_argv = check_docker()
    argv = ["run", "--rm"]
    for opt in ["volume"]:
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
    image_argv = list(image_args)
    for image in images:
        image = f"{DOCKER_NS}/{image}"
        prepare_image(args, docker_argv, image)
        cmd = docker_argv + argv + [image] + image_argv
        if args.pretend:
            print(" ".join(cmd))
        else:
            info(" ".join(cmd))
            ret = subprocess.call(cmd)
            assert ret == 0 or 10 <= ret <= 20, "Solver failed!"
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
    for imageid in images:
        image = f"{DOCKER_NS}/{imageid}"
        info(image)
        prepare_image(args, docker_argv, image)
        container = subprocess.check_output(docker_argv + ["create", image]).decode().strip()
        subprocess.check_call(docker_argv + ["cp", f"{container}:/solvers/", args.output_dir])
        os.rename(os.path.join(args.output_dir, "solvers"),
                os.path.join(args.output_dir, imageid.replace(":","-")))
        check_cmd(docker_argv + ["rm", container])

#
##

##
#
# repository management

class Repository(object):
    def __init__(self, args):
        self.registry, self.setup = fetch_registry(args, open)
        self.images = {}
        for entry in self.registry:
            for solver in self.registry[entry]:
                name = make_name(self.registry, self.setup, entry, solver)
                if hasattr(args, "pattern") and \
                        not fnmatch.fnmatch(name, args.pattern):
                    continue
                self.images[name] = {"entry": entry, "solver": solver}

class ImageManager(object):
    def __init__(self, name, repo):
        self.repo = repo
        self.name = name
        self.entry = repo.images[name]["entry"]
        self.solver = repo.images[name]["solver"]
        self.setup = repo.setup[self.entry].copy()
        self.setup.update(self.setup.get(self.solver, {}))
        self.registry = repo.registry[self.entry][self.solver]

    @property
    def solver_name(self):
        return self.registry["name"]

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

    for name in repo.images:
        image = ImageManager(name, repo)
        setup = image.setup

        fmtvars = {
            "SOLVER": image.solver,
            "SOLVER_NAME": image.solver_name,
        }

        root = str(image.entry)

        build_args = {k:v for k,v in setup.items() if \
                        k not in ["generic_version",
                                    "builder", "builder_base",
                                    "image_name"] and isinstance(v, str)}
        build_args["solver"] = image.solver_name
        build_args["solver_id"] = image.solver
        for k in setup:
            if k in build_args:
                build_args[k] = build_args[k].format(**fmtvars)

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

        base = f"base:{setup['base_version']}"
        if base not in bases_uptodate:
            docker_build(args, docker_argv, f"{DOCKER_NS}/{base}", base.replace(":", "/"))
            bases_uptodate.add(base)

        dist_version = setup.get("dist_version", "v1")
        dist_Dockerfile = f"generic/dist-{dist_version}/Dockerfile"
        dist_args = {
            "BASE": f"{DOCKER_NS}/{base}",
            "BUILDER_BASE": builder_target,
            "IMAGE_NAME": image.name,
            "solver": build_args["solver"],
            "solver_id": build_args["solver_id"],
        }

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
    for dimacs in glob.glob("tests/*.gz"):
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

#
##

def main():
    parser = argparse.ArgumentParser(prog=sys.argv[0])

    parser.add_argument("--refresh-list", default=False, action="store_true",
            help="Force refresh of the list of images")
    parser.add_argument("--pretend", "-p", default=False, action="store_true",
            help="Print Docker commands without executing them")

    subparsers = parser.add_subparsers(help="commands")

    spec_parser = argparse.ArgumentParser(add_help=False)
    spec_parser.add_argument("pattern",
            help="Pattern for filtering images")

    parser_list = subparsers.add_parser("list",
            help=f"List {DOCKER_NS} Docker images")
    parser_list.add_argument("pattern", default="*", nargs="?",
            help="Pattern for filtering images (default: *)")
    parser_list.set_defaults(func=print_list)

    docker_parser = argparse.ArgumentParser(add_help=False)
    docker_parser.add_argument("--pull", action="store_true",
            help="Explicitly pull the image")
    docker_parser.add_argument("-v", "--volume", action="append",
            help="(Docker option) Mount a volume")

    p = subparsers.add_parser("run",
            help=f"Run one or several {DOCKER_NS} Docker images",
            parents=[spec_parser, docker_parser])
    p.add_argument("dimacs",
            help="DIMACS file (possibly gzipped)")
    p.add_argument("proof", nargs="?",
            help="Output file for proof")
    p.set_defaults(func=run_images)

    p = subparsers.add_parser("run-raw",
            help=f"Run one or several {DOCKER_NS} Docker images with direct call to solvers",
            parents=[spec_parser, docker_parser])
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
            parents=[spec_parser, docker_parser])
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
                parents=[spec_parser])
        p.set_defaults(func=build_images)

        p = subparsers.add_parser("test",
                help=f"Test {DOCKER_NS} Docker images",
                parents=[spec_parser, docker_parser])
        p.set_defaults(func=test_images)

        p = subparsers.add_parser("push",
                help=f"Push {DOCKER_NS} Docker images",
                parents=[spec_parser])
        p.set_defaults(func=push_images)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        return parser.print_help()
    return args.func(args)

if __name__ == "__main__":
    main()
