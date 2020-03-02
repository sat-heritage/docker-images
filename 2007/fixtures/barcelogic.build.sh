set -e
sh build.sh
sed -i "s:/bin/sh:/bin/bash:" Barcelogic
cp -v "SatELite_release" "bsat" "Barcelogic" /dist/
