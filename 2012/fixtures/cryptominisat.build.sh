#!/bin/bash
# The CMake of this release asks for MySQL unconditionally, only to log solving
# statistics into a database; the squeeze client library it then links against is
# no longer installable, and the binary refuses to start without it.  The three
# MySQL lines are therefore dropped, which leaves the solver itself untouched.
set -ex
sed -i '/find_package(MySQL/d; /MySQL_INCLUDE_DIR/d; /MySQL_LIB_DIR/d' CMakeLists.txt
sed -i '/MYSQL_LIB/d' cmsat/CMakeLists.txt
grep -rn -i mysql CMakeLists.txt cmsat/CMakeLists.txt || echo "plus aucune référence à MySQL"
mkdir -p build && cd build
cmake ..
make cryptominisat
find . -name cryptominisat -type f -perm -u+x | head -3
