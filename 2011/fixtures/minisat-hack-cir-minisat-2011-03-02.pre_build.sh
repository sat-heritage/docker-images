set -ex
cd /src && d=$(find . -maxdepth 1 -mindepth 1 -type d | head -1) && sed "s|minisat/simp/Main.cc|${d#./}/simp/Main.cc|" minisat.patch-minisat > patch-hack && (patch -p0 --dry-run < patch-hack && patch -p0 < patch-hack) || echo "organizers patch does not apply"
