mv riss7 Riss7
set -x
mkdir debug
mkdir bin
cd debug
cmake -D DRATPROOF=ON ..
make riss-simp
make riss-core

# Copy all scripts to the bin/ directory
cp bin/* ../bin