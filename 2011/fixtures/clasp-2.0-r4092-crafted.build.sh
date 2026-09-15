set -ex
cd /src/clasp-2.0-R4092 && ./configure.sh --strip && cd build/release && make
