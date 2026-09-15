set -ex
cp -v $(find /src/minisat-hacked -name "*_static" -type f | head -1) /dist/RestartSAT
