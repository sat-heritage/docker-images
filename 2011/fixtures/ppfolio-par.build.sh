#!/bin/bash
# ppfolio is a "naive portfolio": the launcher runs five component solvers that
# ship as source archives in src/ and must be built with the submitted script
# before the launcher itself is compiled.  Without them the image answers
# nothing, since ppfolio.cc execs bin/<solver> relative to its own directory.
set -ex
cd src
sh ./buildSolvers.sh
ls -l bin
cd ..
# the default target of the Makefile runs the solver on a missing instance
make ppfolio
