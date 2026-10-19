#!/bin/bash
# PicoSAT configures with configure.sh, which the generic recipe does not
# recognise: it looks for configure, Makefile or makefile, none of which exists
# before that script has run.
set -ex
./configure.sh
make picosat
ls -l picosat
