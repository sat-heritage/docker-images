#!/usr/bin/env python

from __future__ import print_function

from appdirs import user_cache_dir
import argparse
import fnmatch
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from urllib.request import urlopen

DOCKER_NS = "satex"
REGISTRY_BASEURL = "https://raw.githubusercontent.com/sat-heritage/docker-images/master"

cache_validity = 3600*4
cache_dir = user_cache_dir("satex", "satex")
cache_file = os.path.join(cache_dir, "images.json")

on_linux = platform.system() == "Linux"

def error(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)

def info(msg):
    print("+ %s" % msg, file=sys.stderr)

def in_repository():
    return os.path.isfile("index.json")

IN_REPOSITORY = in_repository()

##
#
# List of images

def images_of_registry(reg):
    return [f"{solver}:{tag}" \
                for tag in reg for solver in reg[tag]]

def fetch_list(args, opener):
    with opener("index.json") as fp:
        index = json.load(fp)
    reg = {}
    for tag in sorted(index):
        with opener(f"{tag}/solvers.json") as fp:
            reg[tag] = json.load(fp)
    return images_of_registry(reg)

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
    return fnmatch.filter(images, args.pattern) if hasattr(args, "pattern") \
            else images

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
    if not args.pretend:
        sys.exit(ret)

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
    docker_runs(args, images, docker_args, image_args)

def runraw_images(args):
    images = get_list(args)
    docker_runs(args, images, image_args=["--raw"]+args.args)

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

def build_images(args):
    images = get_list(args)
    argv = ["make"]
    if args.up_to_date:
        argv += ["FROM-update", "base"]
    argv += [f"{image}.build" for image in images]
    info(argv)
    subprocess.check_call(argv)

def test_images(args):
    images = get_list(args)
    argv = ["make"]
    argv += [f"{image}.test" for image in images]
    info(argv)
    subprocess.check_call(argv)

def test_images(args):
    images = get_list(args)
    argv = ["make"]
    argv += [f"{image}.push" for image in images]
    info(argv)
    subprocess.check_call(argv)

def mrproper(args):
    argv = ["make mrproper"]
    info(argv)
    subprocess.check_call(argv)

#
##

def main():
    parser = argparse.ArgumentParser(prog=sys.argv[0])

    parser.add_argument("--refresh-list", default=False, action="store_true",
            help="Force refresh of the list of images")

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
    docker_parser.add_argument("--pretend", "-p", default=False, action="store_true",
            help="Print Docker commands without executing them")
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

    if IN_REPOSITORY:
        p = subparsers.add_parser("build",
                help=f"Build {DOCKER_NS} Docker images",
                parents=[spec_parser])
        p.add_argument("--up-to-date", action="store_true",
                help="Ensure bases are up to date")
        p.set_defaults(func=build_images)

        p = subparsers.add_parser("test",
                help=f"Test {DOCKER_NS} Docker images",
                parents=[spec_parser])
        p.set_defaults(func=test_images)

        p = subparsers.add_parser("push",
                help=f"Push {DOCKER_NS} Docker images",
                parents=[spec_parser])
        p.set_defaults(func=test_images)

        p = subparsers.add_parser("mrproper",
                help="Remove all {DOCKER_NS} Docker images")
        p.set_defaults(func=mrproper)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        return parser.print_help()
    return args.func(args)

if __name__ == "__main__":
    main()
