set -x
set -e
cd /src/cmsat5*
grep -v /opt CMakeLists.txt  > CMakeLists.txt.fixed
mv  CMakeLists.txt.fixed  CMakeLists.txt
