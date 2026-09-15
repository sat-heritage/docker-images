set -ex
cp -v $(find /src/cir_minisat* -name "*_static" -type f | head -1) /dist/cir_minisat
