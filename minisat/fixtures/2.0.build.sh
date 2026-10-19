#!/bin/bash
# The simplifying variant of this release no longer compiles: SimpSolver.C calls
# Clause_new before its declaration, which the two-phase lookup of modern C++
# rejects.  The core solver, which the release also ships, builds as it is.
set -ex
cd core
MROOT=.. make rs
ls -l minisat_static
