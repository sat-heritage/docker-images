#!/bin/bash
# The 1.x releases build with the "rs" target of their single Makefile, which
# links the static minisat_static; that is the target the competitions used.
set -ex
make rs
ls -l minisat_static
