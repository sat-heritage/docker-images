set -ex
# SatELite prints a spurious "s UNSATISFIABLE" on some instances it merely preprocesses
# (a contradiction it later ignores); the script then prints the real answer, which
# leaves two status lines.  Route the preprocessing calls through a wrapper that
# demotes SatELite's status lines to comments; the "+ext" model extension is untouched.
d=$(dirname "$(find /src -name hyperplane_minisat.sh | head -1)")
cat > "$d/se_wrap.sh" <<'WRAP'
#!/bin/bash
exe="$(dirname "$0")/SatELite_release"
case " $* " in *" +ext "*) exec "$exe" "$@";; esac
"$exe" "$@" | sed 's/^s /c SatELite: s /'
exit ${PIPESTATUS[0]}
WRAP
chmod +x "$d/se_wrap.sh"
sed -i 's|^SE=\$mypath/SatELite_release|SE=$mypath/se_wrap.sh|' "$d/hyperplane_minisat.sh"
grep -q 'se_wrap.sh' "$d/hyperplane_minisat.sh"
