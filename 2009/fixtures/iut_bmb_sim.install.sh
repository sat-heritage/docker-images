#!/bin/bash
# Like IUT_BMB_SAT, it prints "s SAT" and "s UNSAT" instead of the competition's
# spelling and always exits 0, so a launcher rewrites the status line and
# returns the expected exit code.
set -ex
install -m 0755 /src/Source/minisat/core/minisat /dist/minisat
install -m 0755 /src/Source/IUT_BMB_SIM/IUT_BMB_SIM /dist/IUT_BMB_SIM
cat > /dist/run-iut_bmb_sim.sh <<'WRAP'
#!/bin/sh
dir=$(dirname "$0")
out=$(mktemp /tmp/iut_bmb_sim.XXXXXX)
(cd "$dir" && ./IUT_BMB_SIM "$1" "${2:-/tmp}") > "$out" 2>&1
if grep -qiE '^s +UNSAT' "$out"; then
    echo "s UNSATISFIABLE"; rm -f "$out"; exit 20
fi
if grep -qiE '^s +SAT' "$out"; then
    echo "s SATISFIABLE"
    grep '^v ' "$out"
    rm -f "$out"; exit 10
fi
cat "$out"; rm -f "$out"
exit 0
WRAP
chmod +x /dist/run-iut_bmb_sim.sh
ls -l /dist
