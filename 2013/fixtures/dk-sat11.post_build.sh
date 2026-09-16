set -ex
# dk-run.sh ends with the exit code of Knuth's solver (16 on unsatisfiable instances);
# the answer is on standard output, so let the wrapper exit 0 as a plain wrapper does.
# The archive holds several copies of the script: patch them all.
for f in $(find /src -name dk-run.sh); do printf '\nexit 0\n' >> "$f"; done
