# SAT Heritage - Docker images of SAT solvers

##  A community-driven effort for archiving, building and running more than thousand SAT solvers

![Solvers count](https://badgen.net/https/github.com/sat-heritage/docker-images/releases/download/list/counter.json)
[![PyPI version](https://badge.fury.io/py/satex.svg)](https://badge.fury.io/py/satex)
[![Docker Hub](https://badgen.net/badge/DockerHub/satex/blue?icon=docker)](https://hub.docker.com/u/satex)
[![Zenodo](https://badgen.net/badge/Zenodo/satex/5cb85c)](https://zenodo.org/communities/satex)

## Principles

SAT research has a long history of source code and binary releases, thanks to competitions organized every year.
However, since every cycle of competitions has its own set of rules and an adhoc way of publishing source code and
binaries, compiling or even running any solver may be harder than what it seems. And there has been more than a thousand solvers published so far, some of them released in the early 90's! 

**This project drives a community-driven effort to archive and to allow easy compilation and running of all SAT solvers
that have been released so far**.  

Thanks to our tool, building (or running) a solver from its source (or from its binary) can be done in one line.

## Usage

Requirements:
* [Docker](https://docker.com)

```
docker run --rm -v $PWD:/data satex/<tool>:<year> <DIMACS> [<PROOF>]
```

## `satex` Python script

Requirements:
* [Python](https://www.python.org/) ≥3.6
* [Docker](https://docker.com)

```
pip install -U satex     # you may have to use pip3
```

In case `satex` commands fails with `command not found` error, try doing `export
PATH=$HOME/.local/bin:$PATH` beforehand.
If it works, add this fixture within your `~/.bashrc` or `~/.profile` file.
See https://packaging.python.org/tutorials/installing-packages/#installing-to-the-user-site

### List images
```
satex list
satex list *:2018
satex list maple*
```

By default, `satex` considers only solvers which have been validated.
Solvers which are not yet validated can be listed with `--unstable` option;
those which are not compiling/working with `--fixme`;
all the referenced solvers are considered with the `--all` option:
```
satex list --fixme      # solvers to be fixed
satex list --unstable   # solvers to be tested
satex list --all        # all referenced solvers
```

### Information

Print information related to solvers, including authors, command line,
validation status. and possibly comments.

```
satex info glucose*
satex info *:2018 --all
```

### Run images
```
satex run cadical:2019 dimacs [proof]
satex run *:2016 dimacs [proof]
satex run *:2009 dimacs -e MAXNBTHREAD=24
```

### Run images with direct call to solvers
```
satex run-raw cadical:2019 -h
```

### Open shell
```
satex shell cadical:2019
```

### Extract solvers binaries
```
satex extract *:2019 /tmp/
```

### Repository management

Usage:
```
satex build *:2018
satex test *:2018
satex push *:2018
```

## Persistent storage for sources and binaries

Consider using [Zenodo](https://zenodo.org) for storing your software, as it provides persistent and versioned URLs.

See https://zenodo.org/communities/satex.


## Adding solvers

Solvers are grouped by sets, typically year of competitions. Each set has its own directory and is referenced in `index.json`.
The minimal structure of a `<set>` directory is the following:
* `<set>/solvers.json`: configuration file for running solvers.
* `<set>/setup.json`: configuration file for building images

### solvers.json

JSON object where keys are the solver identifiers (necessarily in lower case),
and values are JSON objects with the following keys:

| key | type | description |
| --- | --- | --- |
| name | string | Name of the solver, without case restriction |
| call | string | Name of the executable |
| path | string | Directory from which the executable should be called.<br>Default: `name` |
| args | string list | arguments to the executable for simple solving. See below for allowed keywords. |
| argsproof | string list | arguments to the executable for solving with proof output. See below for allowed keywords |
| gz | boolean | If true, the solver supports natively gzipped input files.  If false, an input file ending with `.gz` will be first decompressed by the wrapper script. |


The following keywords are allowed in `args` and `argsproof`:

| keyword | description |
| --- | --- |
| FILECNF | Replaced by the absolute path (within the Docker container) to the input DIMACS file.<br>Whenever the input file ends with `.gz` and `gz` is `False`, the input file is unzipped as `/tmp/gunzipped.cnf` |
| FILEPROOF | Replaced by the absolute path (within the Docker container) to the output file for proof |
| MAXNBTHREAD | Replaced by the `MAXNBTHREAD` environment variable; `1` by default.<br>Example: `satex run asolver:ayear my.cnf -e MAXNBTHREAD=8` |
| MEMLIMIT | Replaced by the `MEMLIMIT` environment variable; `1024` by default. |
| RANDOMSEED | Replaced by the `RANDOMSEED` environment variable; `1234567` by default. |
| TIMEOUT | Replaced by the `TIMEOUT` environment variable; `3600` by default. |

Example
```json
{
    "abcdsat": {
        "name": "abcdSAT_drup",
        "call": "./abcdsat_drup",
        "gz": true,
        "args": [
          "FILECNF"
        ],
        "argsproof": [
          "FILECNF",
          "-certified",
          "-certified-output=FILEPROOF"
        ]
    },
    "lingeling": {
        "call": "./lingeling",
        "name": "Lingelingbbcmain",
        "gz": true,
        "args": [
          "FILECNF"
        ],
        "argsproof": [
          "FILECNF",
          "-t",
          "FILEPROOF"
        ]
    }
}
```

### setup.json

JSON object with the following keys, used by default for each solver.
A solver can override these by adding a key with its identifier and a value
being a JSON object with a subset of the following keys.

| key | description |
| --- | --- |
| base_version | Version of the base image for running the solver (`base/{base_version}`) |
| base_from | Image to inherit from for running the solver |
| builder | Path to the Docker recipe for compiling the solver. If it is not starting with `generic/`, the path is relative to the set directory. The path should contain at least a `Dockerfile`. The builder recipe should install the solver binaries into `/dist`. |
| builder_base | Image to inherit from for compiling the solver |
| image_name | Python format string with ENTRY being the set name and SOLVER the solver identifier<br/>Default: `"{SOLVER}:{ENTRY}"` |
| dist_version | Version of the recipe for assembling the solver image (`generic/dist-{dist_version}`)<br>Default: `"v1"` |
| download_url | Python format string for downloading the solver source/binary |
| BUILD_DEPENDS | Additional packages to install for compiling the solver.<br>Used by `generic/v1` builder |
| RDEPENDS | Additional packages to install for running the executable.<br>Used by `generic/dist-v1` assembler |

Python format strings can use the following variables:
* `SOLVER`: solver identifier (keys in `solvers.json`)
* `SOLVER_NAME`: solver name (specified in `solvers.json`)

The images for running and building the solver (`base_from` and `builder_base`)
are usually Debian distribution of the year of the competition:
see [debian](https://hub.docker.com/_/debian) and [debian/eol](https://hub.docker.com/r/debian/eol/) DockerHub repositories, and
[timeline](https://en.wikipedia.org/wiki/Debian_version_history#Release_timeline) and [detailed history](https://fr.wikipedia.org/wiki/Debian#Historique_des_versions)
of Debian releases.

Example:
```json
{
    "base_version": "v1",
    "base_from": "debian:stretch-slim",
    "builder": "generic/v1",
    "builder_base": "debian:stretch-slim",
    "download_url": "https://zenodo.org/record/abcdef/files/{SOLVER_NAME}.zip?download=1",
    "asolver": {
        "builder": "generic/binary-v1",
        "download_url": "https://github.com/sat-heritage/docker-images/releases/download/packages/{SOLVER_NAME}"
    }
}
```

