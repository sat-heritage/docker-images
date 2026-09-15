set -ex
cp -v $(find /src/Minisat-2.2.0-hack -name "*_static" -type f | head -1) /dist/contrasat_release
