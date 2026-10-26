#!/bin/bash
# The release build of the core solver, as the README asks; the executable is
# named after the version, so rename it to the one the launcher expects.
set -ex
cd core
make clean rs
mv manysat*_static manysat_static
