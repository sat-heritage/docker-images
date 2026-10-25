#!/bin/bash
# Keep the submitted layout: solver.sh calls ./penelope and ./SatELite_release
# from its own directory and takes the instance plus a temporary directory.
set -ex
cp -a . /dist/
chmod 0755 /dist/solver.sh /dist/penelope /dist/SatELite_release 2>/dev/null || true
ls -l /dist
