#!/bin/bash
# The solver writes its answer to a result file and prints nothing usable on
# stdout, as MiniSat does; the competition ran it through SatELiteGTI, which is
# not part of the submission, so a launcher plays that role.
set -ex
install -m 0755 /src/submit/core/aptusat_static /dist/minisat_static
cat > /dist/run-aptusat.sh <<'WRAP'
#!/bin/sh
dir=$(dirname "$0")
result=$(mktemp /tmp/aptusat.XXXXXX)
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
chmod +x /dist/run-aptusat.sh
ls -l /dist
