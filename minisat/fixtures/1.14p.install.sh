#!/bin/bash
# The proof-logging variant writes its result file only when asked with -r, and
# prints a bare SATISFIABLE otherwise, so the launcher passes that option.
set -ex
install -m 0755 minisat_static /dist/minisat_static
cat > /dist/run-minisat.sh <<'WRAP'
#!/bin/sh
dir=$(dirname "$0")
result=$(mktemp /tmp/minisat.XXXXXX)
"$dir/minisat_static" -r "$result" "$1" > /dev/null 2>&1
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
