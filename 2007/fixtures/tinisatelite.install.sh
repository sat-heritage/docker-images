ls -R
set -e
cp -v "SatELite_release" "tinisat" /dist/
cd /dist

echo "#!/bin/bash" > tinisatelite.sh

echo 'if [ "x$1" = "x" ]; then' >> tinisatelite.sh
echo '  echo "USAGE: glucose.sh <input CNF>"' >> tinisatelite.sh
echo ' exit 1' >> tinisatelite.sh
echo 'fi' >> tinisatelite.sh


echo '# to set in evaluation environment' >> tinisatelite.sh
echo 'mypath=.' >> tinisatelite.sh

echo '# To set in a normal envirnement' >> tinisatelite.sh
echo 'mypath=.' >> tinisatelite.sh
echo 'TMP=/tmp/tinisat_$$' >> tinisatelite.sh
echo '' >> tinisatelite.sh
echo 'SE=$mypath/SatELite_release           #set this to the executable of SatELite' >> tinisatelite.sh
echo 'RS=$mypath/tinisat              #set this to the executable of RSat' >> tinisatelite.sh
echo 'INPUT=$1;' >> tinisatelite.sh
echo 'shift' >> tinisatelite.sh
echo 'echo "c"' >> tinisatelite.sh
echo 'echo "c Starting SatElite Preprocessing"' >> tinisatelite.sh
echo 'echo "c"' >> tinisatelite.sh
echo 'echo "$SE $INPUT $TMP.cnf $TMP.vmap $TMP.elim"' >> tinisatelite.sh
echo '$SE $INPUT $TMP.cnf $TMP.vmap $TMP.elim' >> tinisatelite.sh
echo 'X=$?' >> tinisatelite.sh
echo 'echo "c"' >> tinisatelite.sh
echo 'echo "c Starting tinisat"' >> tinisatelite.sh
echo 'echo "c"' >> tinisatelite.sh
echo 'if [ $X == 0 ]; then' >> tinisatelite.sh
echo '  #SatElite terminated correctly' >> tinisatelite.sh
echo '    $RS $TMP.cnf -verbosity=0 $TMP.result "$@"' >> tinisatelite.sh
echo '    #more $TMP.result' >> tinisatelite.sh
echo '  X=$?' >> tinisatelite.sh
echo '  if [ $X == 20 ]; then' >> tinisatelite.sh
echo '    echo "s UNSATISFIABLE"' >> tinisatelite.sh
echo '    rm -f $TMP.cnf $TMP.vmap $TMP.elim $TMP.result' >> tinisatelite.sh
echo '    exit 20' >> tinisatelite.sh
echo '    #Dont call SatElite for model extension.' >> tinisatelite.sh
echo '  elif [ $X != 10 ]; then' >> tinisatelite.sh
echo '    #timeout/unknown, nothing to do, just clean up and exit.' >> tinisatelite.sh
echo '    rm -f $TMP.cnf $TMP.vmap $TMP.elim $TMP.result' >> tinisatelite.sh
echo '    exit $X' >> tinisatelite.sh
echo '  fi' >> tinisatelite.sh
echo '  echo "s SATISFIABLE"' >> tinisatelite.sh
#echo '  $SE +ext $INPUT $TMP.result $TMP.vmap $TMP.elim' >> tinisatelite.sh
echo '  X=10' >> tinisatelite.sh
echo 'elif [ $X == 11 ]; then' >> tinisatelite.sh
echo '  #SatElite died, tinsat must take care of the rest' >> tinisatelite.sh
echo '    $RS $INPUT -verbosity=0 #but we must force tinisat to print out result here!!!' >> tinisatelite.sh
echo '  X=$?' >> tinisatelite.sh
echo 'elif [ $X == 12 ]; then' >> tinisatelite.sh
echo '  #SatElite prints out usage message' >> tinisatelite.sh
echo '  #There is nothing to do here.' >> tinisatelite.sh
echo '  X=0' >> tinisatelite.sh
echo 'fi' >> tinisatelite.sh

echo 'rm -f $TMP.cnf $TMP.vmap $TMP.elim $TMP.result' >> tinisatelite.sh
echo 'exit $X' >> tinisatelite.sh


chmod +x tinisatelite.sh
