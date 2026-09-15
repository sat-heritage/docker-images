set -ex
cd /src/ebminisat && cp -v $(find . -name "*_release" -o -name "*_static" | head -1) /dist/ebminisat_release
