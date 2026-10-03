#!/bin/bash
# Its README says: cd core; gmake rs.  The 2009 organisers built every MiniSat hack with the "rs" target of
# core/, which links the static minisat_static, as their compilation log shows.
set -ex
cd /src/MiniSat2hack/core
make rs
ls -l minisat_static
