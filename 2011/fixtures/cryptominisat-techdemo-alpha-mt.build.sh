set -ex
cd /src/cryptominisat-cryptominisat
sed -i -e "s/CXXFLAGS=\"-g -O3\"/CXXFLAGS=\"-g -O3 -DNDEBUG\"/" configure.in
make -f Makefile.cvs && ./configure && make
