#!/bin/bash
# The solver runs behind its own script, which calls SatELite for
# pre-processing and again for extending the model of a satisfiable formula.
set -ex
cd core
cp -v SatElite manysat.sh manysat_static /dist/
