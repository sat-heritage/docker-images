set -ex
ln -sf $(ls /usr/lib/libtbb.so.* | head -1) /usr/lib/libtbb.so
cd /src/claspmt-2.0-R4095-patched && tar xzf claspmt-2.0-R4095-patched.tar.gz && d=$(find . -maxdepth 1 -mindepth 1 -type d -name "claspmt*" | head -1) && cd $d && ./configure.sh --with-mt TBB_INCLUDE=/usr/include TBB_LIB=/usr/lib && cd build/release_mt && make
