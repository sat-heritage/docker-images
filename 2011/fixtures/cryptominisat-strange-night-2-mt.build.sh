set -ex
cd /src/cryptominisat-cryptominisat
patch -p1 < /src/cryptoms-profile-diff-sn2.patch
sed -i -e "s/CXXFLAGS=\"-g -O3\"/CXXFLAGS=\"-g -O3 -DNDEBUG\"/" configure.in
make -f Makefile.cvs && ./configure && make profile
