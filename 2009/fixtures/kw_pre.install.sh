#!/bin/bash
# The submitted kw_pre script calls kw_preprocessor and minisat by bare name and
# expects TMPDIR to be set.  The launcher provides both and relays the output of
# MiniSat, which already prints the competition s and v lines; the submitted
# script stays beside it untouched.
set -ex
install -m 0755 /src/kw_pre/kw_preprocessor /dist/kw_preprocessor
install -m 0755 /src/kw_pre/minisat /dist/minisat
install -m 0644 /src/kw_pre/kw_pre /dist/kw_pre
cat > /dist/run-kw_pre.sh <<'WRAP'
#!/bin/sh
dir=$(dirname "$0")
tmp=$(mktemp -d /tmp/kw_pre.XXXXXX)
"$dir/kw_preprocessor" "$1" > "$tmp/pre.cnf" 2>/dev/null
"$dir/minisat" "$tmp/pre.cnf"
status=$?
rm -rf "$tmp"
exit $status
WRAP
chmod +x /dist/run-kw_pre.sh
ls -l /dist
