set -ex
# The competition launcher hard-codes the solver directory (/solvers, the competition HOME);
# make it the directory of the script itself, where the image installs solver37.
for f in $(find /src -name solver37.sh); do
  sed -i 's|^vallstdir=/solvers$|vallstdir=$(dirname "$0")|' "$f"
  grep -q 'vallstdir=$(dirname' "$f"
done
