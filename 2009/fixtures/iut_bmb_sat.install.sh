#!/bin/bash
# IUT_BMB_SAT prints "s SAT" and "s UNSAT" instead of the competition's
# "s SATISFIABLE" and "s UNSATISFIABLE", and always exits 0.  A launcher
# rewrites the status line and returns the expected exit code; the solver needs
# its MiniSat next to it and takes the instance plus a temporary directory.
set -ex
install -m 0755 /src/Source/minisat/core/minisat /dist/minisat
install -m 0755 /src/Source/IUT_BMB_SAT/IUT_BMB_SAT /dist/IUT_BMB_SAT
cat > /dist/run-iut_bmb_sat.sh <<'WRAP'
#!/bin/sh
dir=$(dirname "$0")
out=$(mktemp /tmp/iut_bmb_sat.XXXXXX)
(cd "$dir" && ./IUT_BMB_SAT "$1" "${2:-/tmp}") > "$out" 2>&1
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
chmod +x /dist/run-iut_bmb_sat.sh
ls -l /dist
