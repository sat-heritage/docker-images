#!/bin/bash
# Two details of the 2009 submission: its Makefile compiles with "-m32 -static"
# but links without them, which made no difference on the 32-bit machines of the
# time; and its sources use the type "uint", which g++ 4.3 no longer declares.
# The recipe already installs the 4.2 compiler of that era, so use it.
set -ex
make CC="g++-4.2 -m32 -static"
