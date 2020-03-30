set -x
ls -R
mkdir ./bin
make -C code CONF=Release SHARED="-fopenmp -static" penelope_MDLC SatELite
cp code/penelope_MDCL code/SatELite_release code/configuration.ini code/solver.sh /penelope_MDCL/bin