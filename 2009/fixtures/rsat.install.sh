#!/bin/bash
# The competition ran Rsat through its own script, which calls SatElite for
# preprocessing and model extension, so the three files stay side by side.
set -ex
install -m 0755 rsat /dist/rsat
install -m 0755 SatElite /dist/SatElite
install -m 0755 rsat.sh /dist/rsat.sh
ls -l /dist
