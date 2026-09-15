set -ex
cd /src && make clean && make rissExp && cp riss rissExp && make clean && make riss priss
