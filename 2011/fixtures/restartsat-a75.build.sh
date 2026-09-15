set -ex
cd /src/minisat-hacked && export MROOT=$PWD && cd simp && make clean && make rs
