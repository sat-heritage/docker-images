set -ex
cd /src/Minisat-2.2.0-hack && export MROOT=$PWD && cd simp && make clean && make rs
