#!/bin/bash
# Glucose follows the MiniSat layout: the simplifying variant in simp/ is the
# one the competitions ran, and MROOT points at the root of the archive.
set -ex
cd sources/simp
MROOT=.. make rs
ls -l glucose_static
