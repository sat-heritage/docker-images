#!/bin/sh

set -eu

# The submission contains a pre-built binary in bin/.  Install the executable
# produced by the historical builder instead, so this image is source-built.
install -m 0755 build/kissat /dist/kissat
