#!/bin/bash
# The archive unpacks to minisat_BinaryClause090321/.  The 2009 organisers built every MiniSat hack with the "rs" target of
# core/, which links the static minisat_static, as their compilation log shows.
set -ex
cd /src/minisat_BinaryClause090321/core
make rs
ls -l minisat_static
