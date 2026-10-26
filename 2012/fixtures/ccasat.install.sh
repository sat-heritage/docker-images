#!/bin/bash
set -ex
install -m 0755 "$(find . -name CCASat -type f -perm -u+x | head -1)" /dist/CCASat
ls -l /dist
