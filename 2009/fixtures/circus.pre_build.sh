set -x
find /usr/include -name 'zconf.h'
ln -s /usr/include/x86_64-linux-gnu/zconf.h /usr/include
ln -s /usr/include/asm-generic /usr/include/asm
