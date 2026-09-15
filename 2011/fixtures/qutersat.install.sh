set -ex
f=$(find /src/QuteRSat -type f -perm -u+x -size +200k ! -name "*.o" ! -name "*.a" ! -name "*.so*" -printf "%s %p\n" | sort -rn | head -1 | cut -d" " -f2); cp -v "$f" /dist/qutersat_release
