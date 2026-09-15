# SAT Heritage - Docker images of SAT solvers

##  A community-driven effort for archiving, building and running more than thousand SAT solvers

![Solvers count](https://badgen.net/https/github.com/sat-heritage/docker-images/releases/download/list/counter.json)
[![PyPI version](https://badge.fury.io/py/satex.svg)](https://badge.fury.io/py/satex)
[![Docker Hub](https://badgen.net/badge/DockerHub/satex/blue?icon=docker)](https://hub.docker.com/u/satex)
[![Zenodo](https://badgen.net/badge/Zenodo/satex/5cb85c)](https://zenodo.org/communities/satex)
[![Gitter](https://badges.gitter.im/sat-heritage/community.svg)](https://gitter.im/sat-heritage/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)
[![Website](https://badgen.net/badge/website/sat-heritage.github.io/ffd21e)](https://sat-heritage.github.io/docker-images/)
[![Python tests](https://github.com/sat-heritage/docker-images/actions/workflows/python-tests.yml/badge.svg?branch=master)](https://github.com/sat-heritage/docker-images/actions/workflows/python-tests.yml)
[![Image sync](https://github.com/sat-heritage/docker-images/actions/workflows/docker-sync.yml/badge.svg)](https://github.com/sat-heritage/docker-images/actions/workflows/docker-sync.yml)
[![Website build](https://github.com/sat-heritage/docker-images/actions/workflows/pages.yml/badge.svg)](https://github.com/sat-heritage/docker-images/actions/workflows/pages.yml)

## Principles

SAT research has a long history of source code and binary releases, thanks to competitions organized every year.
However, since every cycle of competitions has its own set of rules and an adhoc way of publishing source code and
binaries, compiling or even running any solver may be harder than what it seems. And there has been more than a thousand solvers published so far, some of them released in the early 90's! 

**This project drives a community-driven effort to archive and to allow easy compilation and running of all SAT solvers
that have been released so far**.  

Thanks to our tool, building (or running) a solver from its source (or from its binary) can be done in one line.

## Build policy

Since the SAT Competition 2022 entries, every image is **rebuilt from the
competition sources**. Competition distributions usually ship a precompiled
binary next to the sources; it is never installed in the image unless the
`comment` field of the solver entry says so (for example when no source is
available). The recipe installs the artefact produced by the build, so a
failed build cannot silently fall back to the submitter's binary.

The build runs the scripts submitted to StarExec whenever they exist
(`starexec_build`, `build/build.sh`, `install.sh`, ...) unchanged, as an
unprivileged user like StarExec does. When a script cannot run in our images
(for example because it relies on Red Hat Software Collections), its steps are
transcribed in `setup.json` and the deviation is documented in the solver's
`comment`.

Builds do **not** use CentOS, the operating system of StarExec: they run in a
Debian release of the competition year, pinned by image digest and by a dated
snapshot of the Debian package archive (`APT_SNAPSHOT`), so that the compiler
and libraries are those available at competition time and the build is
reproducible. Solver images run on the same Debian base.

Entries of 2021 and earlier predate this policy: their recipes were written by
hand with the `generic/v1` builder, whose heuristics may install binaries
shipped in the archive (`binary/` or `bin/` directories), and a few sets use
the `generic/binary-*` builders for binary-only releases.

## Usage

Requirements:
* [Docker](https://docker.com)

```
docker run --rm -v $PWD:/data satex/<tool>:<year> <DIMACS> [<PROOF>]
```

## `satex` Python script

Requirements:
* [Python](https://www.python.org/) 3.10–3.14
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
satex list '*:2018'
satex list 'maple*'
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
satex info 'glucose*'
satex info '*:2018'
```

### Run images
```
satex run cadical:2019 dimacs [proof]
satex run '*:2016' dimacs [proof]
satex run '*:2009' dimacs -e MAXNBTHREAD=24
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
satex extract '*:2019' /tmp/
```

### Repository management

Usage:
```
satex build '*:2018'
satex test '*:2018'
satex push '*:2018'
```

`satex test` runs a SAT instance (plain and gzip-compressed), an UNSAT
instance, and, when supported by the image, an UNSAT proof check.  A timeout,
an invalid return code, a contradictory status, an invalid SAT model, or an
invalid proof makes the command fail.
Tests run in a temporary workspace, so files created by legacy solvers do not
pollute the repository.

Validate the registry metadata and run the Python regression tests with:

```
pip install -r requirements-dev.txt
python tools/validate_metadata.py
python -m unittest discover -s tests -v
```

The JSON schemas are stored in `schemas/`.  Solver statuses are restricted to
`ok`, `unknown`, `unstable`, and `fixme`; legacy details are kept in
`status_detail`.

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
| test_timeout | Minimum timeout in seconds used by `satex test` for this solver, for submissions whose preprocessing is slow even on tiny inputs (the command-line `--timeout` still applies when larger) |
| incomplete | boolean | true for incomplete solvers (local search, portfolios without complete solver): `satex test` runs them on an easy satisfiable instance and skips the UNSAT checks, which they cannot pass |
| license | string | SPDX identifier(s) of the licence the solver is distributed under, several joined with ` AND ` (for example `MIT`, `GPL-3.0`). Filled by `tools/detect_licenses.py` from the licence files and source headers of the archive; correct or complete it by hand when you know better |
| license_source | string | where the licence was read: a licence file or source header of the archive, a paper, the authors |


The following keywords are allowed in `args` and `argsproof`:

| keyword | description |
| --- | --- |
| FILECNF | Replaced by the absolute path (within the Docker container) to the input DIMACS file.<br>Whenever the input file ends with `.gz` and `gz` is `False`, the input file is unzipped as `/tmp/gunzipped.cnf` |
| FILEPROOF | Replaced by the absolute path (within the Docker container) to the output file for proof |
| PROOFDIR | Replaced by a temporary directory; after the run, `proof.out` in that directory is moved to the `FILEPROOF` path. This is the StarExec convention for run scripts that take an output directory as second argument |
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
| APT_SNAPSHOT | Timestamp (`YYYYMMDDThhmmssZ`) of the [snapshot.debian.org](https://snapshot.debian.org) archive used for installing packages, so that recent entries are compiled with the toolchain available at competition time. Requires `APT_CODENAME`.<br>Used by `base/v1`, `generic/v1`, `generic/dist-v1` and `generic/starexec-v2` |
| APT_CODENAME | Debian codename (for example `bullseye`) matching `APT_SNAPSHOT` |
| BUILD_KIND | Build method for the `generic/starexec-v2` builder: `auto` (default, detected from the archive), `starexec` (`starexec_build`), `build-subdir` (`build/build.sh`), `script` (`BUILD_SCRIPT`), `configure` (`./configure` then `make`), `make` or `command` (`BUILD_COMMAND`) |
| BUILD_SUBDIR | Directory, relative to the root of the submission archive, where the build is run.<br>Default: `.` |
| BUILD_SCRIPT, BUILD_ARGS, CONFIGURE_ARGS, MAKE_ARGS, BUILD_COMMAND | Parameters of the corresponding `BUILD_KIND` |
| BUILD_ENV | Shell variable assignments exported before running the build, for example `CC="gcc -fcommon"` to compile code written for pre-GCC 10 compilers with the submitted script unchanged; the builder exports `MAKEFLAGS=-j8` by default, use `MAKEFLAGS=` here to build serially |
| BINARY_PATH | Path, relative to the root of the submission archive, of the executable produced by the build. It is installed in `/dist`, so the precompiled binaries shipped in competition archives are never used.<br>Required by `generic/starexec-v2` |
| BINARY_NAME | Name of the installed executable.<br>Default: basename of `BINARY_PATH` |
| DIST_PATHS | Space-separated paths, relative to the root of the submission archive, copied into `/dist` with their relative layout, for submissions whose run script drives several programs (for example `bin kissat/build/kissat`). May replace `BINARY_PATH`.<br>Used by `generic/starexec-v2` |

The `generic/starexec-v2` builder is intended for StarExec submissions of
recent competitions (2022 onwards): one ZIP archive per solver, whose top-level
directory is the solver name, and per-solver build parameters declared in
`setup.json` instead of fixture scripts.

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


## License

The Docker images are for academic and educational use only.

The `satex` (`satex.py`) program is distributed under the MIT license. Please see the
[LICENSE](LICENSE) file for more details.
