#!/bin/bash
# The description says the solver was submitted as a 32-bit version; its Makefile
# asks for "-static" but not for "-m32", so the flag is added here, as the 2009
# entries of the same solver do.  sys/types.h is pulled in because the sources
# use the type "uint", which the headers of squeeze no longer declare on their
# own in C++.
set -ex
make CC="g++ -m32 -static -include sys/types.h"
ls -l SApperloT2010
