set -ex

# MiniSat 2.0 beta prints a bare SATISFIABLE/UNSATISFIABLE and no model unless a result file is
# given: a wrapper runs it with a temporary result file and prints the competition lines from it.
# The wrapper is written next to every copy of the binary so that the installed one has it.
for b in $(find /src -type f -perm /100 -name minisat_static); do
cat > "$(dirname "$b")/run-lysat.sh" <<'WRAP'
#!/bin/bash
d="$(dirname "$0")"; res="/tmp/minisat_static.$$.res"
"$d/minisat_static" "$1" "$res"; rc=$?
if [ -f "$res" ]; then
  case "$(head -1 "$res")" in
    SAT) echo "s SATISFIABLE"; sed -n '2p' "$res" | sed 's/^/v /';;
    UNSAT) echo "s UNSATISFIABLE";;
  esac
  rm -f "$res"
fi
exit $rc
WRAP
chmod +x "$(dirname "$b")/run-lysat.sh"
done
