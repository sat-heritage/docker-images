set -ex
e=`find /src -name 'build.sh' -printf '%h\n'`
cd ${e}
mv -v binary/* /dist/
