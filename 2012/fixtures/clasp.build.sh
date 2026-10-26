#!/bin/bash
# The source release configures with its own script and builds into build/release.
set -ex
./configure.sh --config=release
make -C build/release
find . -name clasp -type f -perm -u+x | head -3
