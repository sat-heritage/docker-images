set -ex
e=`find /src -name binary -type d -printf '%h\n'|sort|head -n1`
cd ${e}
mv -v binary/* /dist/
