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

