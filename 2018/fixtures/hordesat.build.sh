tar xvf lingeling-bbc-9230380-160707.tar.gz
mv lingeling-bbc-9230380-160707 lingeling
cd lingeling
./configure.sh
make
cd ..

# make hordesat
cd hordesat-src
make
cd ..
mkdir bin
mv hordesat-src/hordesat bin
