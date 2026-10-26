#!/bin/bash
# The archive carries its own configure script, named configure, and builds the
# sequential solver together with its parallel driver; Treengeling appears only
# in the later releases.
set -ex
./configure
make lingeling plingeling
ls -l lingeling plingeling
