#!/bin/bash
set -ex
install -m 0755 "$(find build -name cryptominisat -type f -perm -u+x | head -1)" /dist/cryptominisat
ls -l /dist
