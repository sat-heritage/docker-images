#!/bin/bash
# The archive unpacks to core/ and mtl/ at the top level.  The 2009 organisers
# built these MiniSat hacks with the "rs" target, which links the static
# minisat_static: their own compilation log of the competition shows
# "cd core; make clean; make rs" for both cumr variants.
set -ex
cd /src/core
make rs
ls -l minisat_static
