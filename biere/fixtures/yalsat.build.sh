#!/bin/bash
# YalSAT configures with configure.sh, which the generic recipe does not look
# for, and its version script reads a git identity the archive does not carry.
set -ex
./configure.sh
make yalsat
ls -l yalsat
