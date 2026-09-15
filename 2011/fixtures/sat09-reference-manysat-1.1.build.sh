set -ex
cd /src/BLOCKED && export MROOT=$PWD && cd core && make clean rs && mv manysat*_static manysat_static
