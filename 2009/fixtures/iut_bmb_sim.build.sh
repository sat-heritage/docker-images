#!/bin/bash
# Same shape as IUT_BMB_SAT: the archive unpacks to Binary/ and Source/, and the
# submission builds MiniSat first, then its single source file.  The archive also
# ships a 32-bit object left over from the submitters' own build, which the link
# step would mix with fresh 64-bit ones, so start from clean.
set -ex
cd /src
rm -f Source/minisat/core/*.o
make -C Source/minisat/core
g++ -O2 -o Source/IUT_BMB_SIM/IUT_BMB_SIM Source/IUT_BMB_SIM/New_Factoring.cpp
ls -l Source/minisat/core/minisat Source/IUT_BMB_SIM/IUT_BMB_SIM
