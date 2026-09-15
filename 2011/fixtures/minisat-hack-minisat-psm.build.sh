set -ex
cd /src/minisatPsmDyn/core && rm -f SatELite_release minisat_static && tar xzf satelite.tgz && sd=$(find . -maxdepth 1 -mindepth 1 -type d ! -name core | head -1) && find $sd -name depend.mak -delete && (cd $sd && export FM=$PWD/ForMani && cd SatELite && make r && cp SatELite_release ../../) && export MROOT=$PWD/.. && make rs
