set -ex
tar -xvzf 2000-Asat.src.tgz
cd asat.src
make
cp -v Asat /dist/
