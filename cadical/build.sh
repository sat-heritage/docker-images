#!/bin/bash
# CaDiCaL configures and builds into build/; only the solver binary is kept.
set -ex
./configure
make cadical
ls -l build/cadical
