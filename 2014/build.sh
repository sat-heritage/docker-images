set -ex
e=`find /src -name 'build.sh' -printf '%h\n'|sort|head -n1`
cd ${e}
bash build.sh
