set -e
bash build.sh
mv /src/tinisatelite.TiniSatELite TiniSatELite
cp -v "SatELite_release" "tinisat" "TiniSatELite" /dist/
