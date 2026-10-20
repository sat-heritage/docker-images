#!/bin/bash
# This release predates the competition output format: it prints SATISFIABLE or
# UNSATISFIABLE on its own, the assignment as bare lines of literals, and sets
# the exit code to 10 or 20.  A launcher turns that into the s and v lines.
set -ex
install -m 0755 limmat /dist/limmat
cat > /dist/run-limmat.sh <<'WRAP'
#!/bin/sh
dir=$(dirname "$0")
out=$(mktemp /tmp/limmat.XXXXXX)
"$dir/limmat" "$@" > "$out" 2>&1
status=$?
if [ "$status" -eq 20 ]; then
    echo "s UNSATISFIABLE"; rm -f "$out"; exit 20
fi
if [ "$status" -eq 10 ]; then
    echo "s SATISFIABLE"
    grep -E '^ *-?[0-9]+( +-?[0-9]+)* *$' "$out" | tr -s ' \n' ' ' | sed 's/^ *//; s/ *$//; s/^/v /; s/$/ 0/'
    rm -f "$out"; exit 10
fi
cat "$out"; rm -f "$out"
exit $status
WRAP
chmod +x /dist/run-limmat.sh
ls -l /dist
