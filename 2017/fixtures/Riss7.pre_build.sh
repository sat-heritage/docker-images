mv riss7 Riss7
set -x
echo "mkdir debug" > Riss7/starexec_build
echo "mkdir bin" >> Riss7/starexec_build
echo "cd debug" >> Riss7/starexec_build
echo "cmake -D DRATPROOF=ON .. " >> Riss7/starexec_build
echo "make riss-simp" >> Riss7/starexec_build
echo "make riss-core" >> Riss7/starexec_build

# Copy all scripts to the bin/ directory
echo "cp bin/* ../bin" >> Riss7/starexec_build