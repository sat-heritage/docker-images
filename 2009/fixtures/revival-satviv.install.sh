#!/bin/bash
# Keep the submitted layout: run.sh calls ./revival, ./SatElite and ./minisat
# from its own directory, and takes the instance plus a temporary directory.
set -ex
cp -a /src/ReVivAl-SatViv/. /dist/
chmod 0755 /dist/run.sh /dist/revival /dist/SatElite /dist/minisat
ls -l /dist
