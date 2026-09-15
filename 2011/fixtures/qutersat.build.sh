set -ex
cd /src/QuteRSat && grep -rl -- "-ltermcap" --include=Makefile* . | xargs -r sed -i "s/-ltermcap/-lncurses/g" && make
