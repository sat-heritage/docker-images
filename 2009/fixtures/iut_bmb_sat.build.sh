#!/bin/bash
# The archive unpacks to Binary/ and Source/ at the top level.  The submission
# README gives the two build steps: build MiniSat, then compile the single file
# of IUT_BMB_SAT; the solver expects both binaries side by side.  The archive
# also ships a 32-bit Solver.o left over from the submitters' own build, which
# the link step would mix with fresh 64-bit objects, so start from clean.
set -ex
cd /src
rm -f Source/minisat/core/*.o
make -C Source/minisat/core
g++ -O2 -o Source/IUT_BMB_SAT/IUT_BMB_SAT Source/IUT_BMB_SAT/New_Factoring.cpp
ls -l Source/minisat/core/minisat Source/IUT_BMB_SAT/IUT_BMB_SAT
