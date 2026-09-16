ls -R
set -e
cp -v "SatELite_release" "tinisat" /dist/
cd /dist

# The competition launcher (TiniSatELite, kept in fixtures/tinisatelite.TiniSatELite) runs
# tinisat with a result file and extends the model with SatELite +ext, but this build of
# tinisat ignores the result file argument.  The script below keeps the same structure and
# turns tinisat's own "v" line into the result file that SatELite +ext expects, so that the
# model of the original instance is printed.
cat > tinisatelite.sh <<'SCRIPT'
#!/bin/bash
if [ "x$1" = "x" ]; then
  echo "USAGE: tinisatelite.sh <input CNF>"
  exit 1
fi
mypath=.
TMP=/tmp/tinisat_$$
SE=$mypath/SatELite_release
RS=$mypath/tinisat
INPUT=$1;
shift
echo "c"
echo "c Starting SatElite Preprocessing"
echo "c"
$SE $INPUT $TMP.cnf $TMP.vmap $TMP.elim
X=$?
echo "c"
echo "c Starting tinisat"
echo "c"
if [ $X == 0 ]; then
  #SatElite terminated correctly
  $RS $TMP.cnf "$@" > $TMP.out
  X=$?
  grep -v '^[sv] ' $TMP.out
  if [ $X == 20 ]; then
    echo "s UNSATISFIABLE"
    rm -f $TMP.cnf $TMP.vmap $TMP.elim $TMP.result $TMP.out
    exit 20
  elif [ $X != 10 ]; then
    #timeout/unknown, nothing to do, just clean up and exit.
    rm -f $TMP.cnf $TMP.vmap $TMP.elim $TMP.result $TMP.out
    exit $X
  fi
  # SATISFIABLE: rebuild a result file from tinisat's model and let SatELite extend it
  { echo SAT; grep '^v ' $TMP.out | sed 's/^v //' | tr '\n' ' '; echo; } > $TMP.result
  $SE +ext $INPUT $TMP.result $TMP.vmap $TMP.elim
  X=10
elif [ $X == 11 ]; then
  #SatElite died, tinisat must take care of the rest
  $RS $INPUT
  X=$?
elif [ $X == 12 ]; then
  #SatElite prints out usage message
  X=0
fi
rm -f $TMP.cnf $TMP.vmap $TMP.elim $TMP.result $TMP.out
exit $X
SCRIPT
chmod +x tinisatelite.sh
