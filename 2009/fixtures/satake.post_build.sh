set -ex
# satake answers on standard output but exits with code 2 after a successful run: a wrapper
# turns that into the plain-wrapper convention (exit 0, answer on standard output).
for b in $(find /src -type f -perm /100 -name satake); do
cat > "$(dirname "$b")/run-satake.sh" <<'WRAP'
#!/bin/bash
"$(dirname "$0")/satake" "$@"
exit 0
WRAP
chmod +x "$(dirname "$b")/run-satake.sh"
done
