#!/bin/bash
# The 2.1 archive keeps the solver under sources/glucose; its core directory is
# the one whose Makefile builds glucose, the simp one still builds minisat.
set -ex
cd sources/glucose/core
make rs
ls -l glucose_static
