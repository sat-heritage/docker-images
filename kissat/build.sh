#!/bin/bash
# Kissat configures and builds into build/; only the solver binary is kept.
set -ex
./configure
make kissat
ls -l build/kissat
