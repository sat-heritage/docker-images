set -ex
cd /src
files=$(ls)
mkdir mxc
mv ${files} mxc
cd mxc
sed -i 's:include <stdlib.h>:include <stdlib.h>#include <stdint.h>#include <ctype.h>:' mxc-sat09.cpp
bash compile.sh
