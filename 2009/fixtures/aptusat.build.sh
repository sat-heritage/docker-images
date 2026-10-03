#!/bin/bash
# The archive unpacks to submit/, holding core/ and mtl/.  The 2009 organisers
# built every MiniSat hack with the "rs" target of core/, as their compilation
# log shows; here the Makefile names the executable aptusat.
set -ex
cd /src/submit/core
make rs
ls -l aptusat_static
