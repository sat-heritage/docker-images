#!/bin/bash
# Run as its README says, the solver prints a bare "SATISFIABLE" and no model.
# With a result file it writes "SAT" and the model, so a launcher turns that into
# the competition output.
set -ex
install -m 0755 /src/MiniSat2hack/core/minisat_static /dist/minisat_static
cat > /dist/run-minisat2hack.sh <<'WRAP'
#!/bin/sh
dir=$(dirname "$0")
result=$(mktemp /tmp/minisat2hack.XXXXXX)
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
chmod +x /dist/run-minisat2hack.sh
ls -l /dist
