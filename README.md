# SAT Heritage - Docker images

[![PyPI version](https://badge.fury.io/py/satex.svg)](https://badge.fury.io/py/satex)

[Docker HUB](https://hub.docker.com/u/satex)

## Usage

Requirements:
* [Docker](https://docker.com)

```
docker run --rm -v $PWD:/data satex/<tool>:<year> <DIMACS> [<PROOF>]
```

## `satex` Python script

```
pip install -U satex     # you may have to use pip3
```

### List images
```
satex list
satex list *:2018
satex list maple*
```

### Run images
```
satex run cadical:2019 dimacs [proof]
satex run *:2016 dimacs [proof]
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

Alternative installation:
```
pip install --user -e .
```

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
| gz | boolean | If true, the solver supports natively gzipped input files.  If false, an input file ending with `.gz` will be first decompressed by the wrapper script. |
| args | string list | arguments to the executable for simple solving. `FILECNF` will be replaced by the input filename. |
| argsproof | string list | arguments to the executable for solving with proof output `FILEPROOF` |


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
A solver can use specific values by adding a key with its identifier and a value
being a JSON object with a subset of the following keys.

| key | description |
| --- | --- |
| base_version | Version (tag) of the base image for running the solver available in the `base/` directory |
| generic_version | Name of the generic recicpe for building the solver available in the `generic/` directory |
| builder_base | Image to inherit from for compiling the solver |
| builder | If specified, gives the path for the Docker recipe for building the solver. It should contain at least a `Dockerfile`<br/>(optional) |
| image_name | Python format string with ENTRY being the set name and SOLVER the solver identifier<br/>Default: `"{SOLVER}:{ENTRY}"` |
| archive_baseurl | Prefix of the URL to download solver sources <br/>(Used by generic `v1`) |
| download_url | Pattern of the URL  <br/>(Used by generic `binary-v1`, `2000`) |


Example:
```json
{
    "base_version": "potato",
    "generic_version": "binary-v1",
    "builder_base": "debian/eol:potato",
    "download_url": "https://zenodo.org/record/3676454/files/{SOLVER_NAME}?download=1",
    "asat": {
        "generic_version": "2000",
        "download_url": "https://github.com/sat-heritage/docker-images/releases/download/packages/2000-{SOLVER_NAME}.src.tgz"
    }
}
```

