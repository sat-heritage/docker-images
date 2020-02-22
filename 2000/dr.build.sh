set -ex
tar -xvzf 2000-bdrdp.src.tgz
cd bdrdp.src
make dr dll-dr
cp -v dr dll-dr /dist/
