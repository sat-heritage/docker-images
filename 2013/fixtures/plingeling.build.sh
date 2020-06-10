#!/bin/sh
mkdir /src/binary
cd code
./configure || exit 1
make || exit 1
cp /src/code/plingeling /src/binary
