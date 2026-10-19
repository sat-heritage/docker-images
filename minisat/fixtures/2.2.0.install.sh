#!/bin/bash
# MiniSat prints a bare SATISFIABLE and no model, as the competitions of the
# time accepted; with a result file it writes SAT or UNSAT and the model, so a
# launcher turns that into the s and v lines, exactly as the MiniSat hacks of
# 2009 are handled.
set -ex
install -m 0755 simp/minisat_static /dist/minisat_static
cat > /dist/run-minisat.sh <<'WRAP'
#!/bin/sh
dir=$(dirname "$0")
result=$(mktemp /tmp/minisat.XXXXXX)
"$dir/minisat_static" "$1" "$result" > /dev/null 2>&1
status=$?
if grep -qiE '^(c *)?UNSAT' "$result"; then
    echo "s UNSATISFIABLE"; rm -f "$result"; exit 20
fi
if grep -qiE '^(c *)?SAT' "$result"; then
    echo "s SATISFIABLE"
    grep '^v ' "$result" || sed -n '2p' "$result" | sed 's/^/v /'
    rm -f "$result"; exit 10
fi
rm -f "$result"
exit $status
WRAP
chmod +x /dist/run-minisat.sh
ls -l /dist
