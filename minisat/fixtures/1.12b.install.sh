#!/bin/bash
# This release takes no result file and prints no model: only the words
# SATISFIABLE or UNSATISFIABLE, after its statistics.  The launcher turns those
# into the s line, which is all this version can tell.
set -ex
install -m 0755 minisat_static /dist/minisat_static
cat > /dist/run-minisat.sh <<'WRAP'
#!/bin/sh
dir=$(dirname "$0")
out=$(mktemp /tmp/minisat.XXXXXX)
"$dir/minisat_static" "$1" > "$out" 2>&1
if grep -qE '^UNSATISFIABLE' "$out"; then
    echo "s UNSATISFIABLE"; rm -f "$out"; exit 20
fi
if grep -qE '^SATISFIABLE' "$out"; then
    echo "s SATISFIABLE"; rm -f "$out"; exit 10
fi
cat "$out"; rm -f "$out"
exit 0
WRAP
chmod +x /dist/run-minisat.sh
ls -l /dist
