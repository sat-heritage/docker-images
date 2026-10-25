#!/bin/bash
# The archive unpacks the sources under a CCASat directory, with a build script.
set -ex
ls -l
if test -f build.sh; then bash ./build.sh; else make || g++ -O3 -o CCASat *.cpp; fi
find . -name CCASat -type f -perm -u+x | head -3
