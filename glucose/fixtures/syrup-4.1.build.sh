#!/bin/bash
# The parallel release builds from its parallel directory, which links
# glucose-syrup_static.
set -ex
cd parallel
MROOT=.. make rs
ls -l glucose-syrup_static
