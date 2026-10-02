#!/bin/bash
# CirCUs builds 32-bit (-m32 -static) and links against -ll, the library of the
# original AT&T lex.  Debian ships flex instead, and no 32-bit build of its
# library, so provide the single symbol CirCUs needs from it.
set -ex
printf 'int yywrap(void){return 1;}\n' > yywrap.c
gcc -m32 -c yywrap.c -o yywrap.o
sed -i 's/-ll\b/yywrap.o/' Makefile
make
