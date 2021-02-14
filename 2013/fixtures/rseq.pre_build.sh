set -ex
sed -i 's/^icc/gcc/' $(find -name build.sh)
