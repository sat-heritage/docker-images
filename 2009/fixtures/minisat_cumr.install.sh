#!/bin/bash
# minisat_cumr is a MiniSat 1.x hack: it writes its answer to a result file as
# "c SAT" or "c UNSAT" followed by a v line, and prints nothing usable on
# stdout.  The competition ran it through SatELiteGTI, which is not part of the
# submission, so a small launcher plays that role.
set -ex
install -m 0755 /src/core/minisat_static /dist/minisat_static
cat > /dist/run-minisat_cumr.sh <<'WRAP'
#!/bin/sh
dir=$(dirname "$0")
result=$(mktemp /tmp/minisat_cumr.XXXXXX)
"$dir/minisat_static" "$1" "$result" > /dev/null 2>&1
status=$?
if grep -qiE '^c *UNSAT' "$result"; then
    echo "s UNSATISFIABLE"; rm -f "$result"; exit 20
fi
if grep -qiE '^c *SAT' "$result"; then
    echo "s SATISFIABLE"
    grep '^v ' "$result"
    rm -f "$result"; exit 10
fi
rm -f "$result"
exit $status
WRAP
chmod +x /dist/run-minisat_cumr.sh
ls -l /dist
