set -ex
# The certified-UNSAT build of glucose 2.3 has no -model flag: on satisfiable instances it
# prints "SAT" followed by the assignment on a bare line.  A wrapper turns that line into a
# "v" line; the DRUP proof lines it prints before the answer are left untouched.
d=$(dirname "$(find /src -type f -perm /100 -name glucose | head -1)")
cat > "$d/run-glucose-drup.sh" <<'WRAP'
#!/bin/bash
"$(dirname "$0")/glucose" "$@" | awk '/^SAT$/ {m=1; next} m==1 {print "v " $0; m=0; next} {print}'
exit ${PIPESTATUS[0]}
WRAP
chmod +x "$d/run-glucose-drup.sh"
