set -ex
cd /src && patch -p0 < minisat.patch-minisat && cd minisat && export MROOT=$PWD && cd simp && make rs
