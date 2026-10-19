#!/bin/bash
# The build script of the archive first builds the SatELite of its ForMani
# framework, which no longer compiles (its generated depend.mak is missing).
# The solver itself builds, so only that part of the script is run; the image
# therefore holds Glucose alone, without the preprocessing the 2009 entry ran.
set -ex
cd sources/glucose/core
make rs
ls -l glucose_static
