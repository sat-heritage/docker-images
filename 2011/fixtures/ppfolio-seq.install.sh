#!/bin/bash
# Keep the competition layout: the launcher at the root of the image directory
# and its component solvers in bin/, which is where ppfolio.cc looks for them.
set -ex
mkdir -p /dist/bin
mv src/bin/* /dist/bin/
mv ppfolio /dist/
ls -l /dist /dist/bin
