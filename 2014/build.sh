set -ex
e=`find /src -name 'build.sh' -printf '%h\n'|head -n1`
cd ${e}
bash build.sh
