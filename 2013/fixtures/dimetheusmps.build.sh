#!/bin/bash
set -ex
# The archive ships a binary built with -march=native on the author's machine (illegal
# instruction elsewhere) and its Makefile uses -march=native too: rebuild for a generic x86-64.
cd ./code/src
sed -i 's/-march=native/-march=x86-64 -mtune=generic/' Makefile
rm -f ../bin/dimetheus
make clean || true
make
cd ../../
mkdir -p binary
rm -rf ./binary/*
mv ./code/bin/dimetheus ./binary/DimetheusMPS
