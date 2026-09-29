#!/bin/bash
# CMake build of the archive, the one its author uses (INSTALL file), in the
# Release configuration: USE_GAUSS stays disabled as in constants.h, and the
# Gauss and Logger sources, which do not compile without it, are left out.
# The autotools build compiles them, hence the patches of the SAT Museum.
set -ex
cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make
