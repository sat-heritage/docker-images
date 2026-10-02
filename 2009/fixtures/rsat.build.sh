#!/bin/bash
# Three problems with this submission.  Its SatELite sources are rejected by the
# compilers Debian still ships ("explicit template specialization cannot have a
# storage class"), but the submission also contains the SatElite binary the
# authors used, so that one is kept as submitted.  At -O3 the compiler hits an
# internal compiler error on manager.cpp, so Rsat is built at -O2.  And
# utils.cpp calls clock() without including <ctime>, which older compilers
# pulled in through another header.
set -ex
make rsat CFLAGS="-O2 -fomit-frame-pointer -include ctime"
test -x rsat
test -x SatElite
ls -l rsat SatElite rsat.sh
