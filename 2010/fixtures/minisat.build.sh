#!/bin/bash
# The 2.x releases split the solver in core/ and simp/; the simplifying variant
# is the one the competitions ran.  MROOT points at the root of the archive.
set -ex
cd simp
MROOT=.. make rs
ls -l minisat_static
