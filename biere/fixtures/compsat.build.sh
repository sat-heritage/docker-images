#!/bin/bash
# The default target also builds the "example" and "test" programs of the
# distribution, which no longer compile; the solver itself does.
set -ex
./configure
make compsat
ls -l compsat
