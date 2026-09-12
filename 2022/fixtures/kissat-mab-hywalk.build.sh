#!/bin/sh

set -eu

# The official submission ships configure without its executable bit and a
# generated makefile containing the submitter's absolute build path.  Its
# helper scripts also lost their executable bits in the competition ZIP.
chmod +x configure scripts/*.sh
sh ./configure
make
