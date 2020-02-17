set -ex
tar -xvzf asat.src.tgz
cd asat.src
make
cp -v Asat /dist/
