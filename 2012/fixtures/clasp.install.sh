#!/bin/bash
# clasp prints the competition lines but exits 30 where the format expects 10 or
# 20, since its own exit codes serve answer-set programming.  A launcher relays
# its output and returns the code the status line calls for.
set -ex
install -m 0755 "$(find . -name clasp -type f -perm -u+x | head -1)" /dist/clasp
cat > /dist/run-clasp.sh <<'WRAP'
#!/bin/sh
dir=$(dirname "$0")
out=$(mktemp /tmp/clasp.XXXXXX)
"$dir/clasp" "$@" > "$out" 2>&1
cat "$out"
if grep -qE '^s UNSATISFIABLE' "$out"; then rm -f "$out"; exit 20; fi
if grep -qE '^s SATISFIABLE' "$out"; then rm -f "$out"; exit 10; fi
rm -f "$out"
exit 0
WRAP
chmod +x /dist/run-clasp.sh
ls -l /dist
