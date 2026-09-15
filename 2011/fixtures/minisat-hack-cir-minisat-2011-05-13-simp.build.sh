set -ex
cd /src/cir_minisat* && export MROOT=$PWD && cd simp && make clean && make rs
