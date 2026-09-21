#!/bin/bash
# Keep the competition layout: the launcher at the root of the image directory
# and its component solvers in bin/, where ppfolio looks for them.
set -ex
mkdir -p /dist/bin
cp -a bin/. /dist/bin/
cp -a ppfolio /dist/
ls -l /dist /dist/bin
