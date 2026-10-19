#!/bin/bash
# The C translation of 1.14 takes no result file: it prints SATISFIABLE or
# UNSATISFIABLE, then its model as zero-based assignments "x0=0 x1=1", and it
# always exits 0.  The launcher reads that and prints the s and v lines, with
# variables numbered from one as DIMACS does.
set -ex
install -m 0755 minisat_static /dist/minisat_static
cat > /dist/run-minisat.sh <<'WRAP'
#!/bin/sh
dir=$(dirname "$0")
out=$(mktemp /tmp/minisat-c.XXXXXX)
"$dir/minisat_static" "$1" > "$out" 2>&1
if grep -qE '^UNSATISFIABLE' "$out"; then
    echo "s UNSATISFIABLE"; rm -f "$out"; exit 20
fi
if grep -qE '^SATISFIABLE' "$out"; then
    echo "s SATISFIABLE"
    sed -n 's/^Satisfying solution: *//p' "$out" | tr ' ' '\n' | sed -n 's/^x\([0-9]*\)=\([01]\)$/\1 \2/p' |
        awk '{ v = $1 + 1; printf "%s%d ", ($2 == 1 ? "" : "-"), v } END { print "0" }' | sed 's/^/v /'
    rm -f "$out"; exit 10
fi
cat "$out"; rm -f "$out"
exit 0
WRAP
chmod +x /dist/run-minisat.sh
ls -l /dist
