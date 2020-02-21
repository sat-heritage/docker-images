#!/bin/bash
exe="${0}.out"
if [[ "${1}" == "--satex" ]]; then
    shift
    grep -v "^[cp]" "${1}" | sed 's/-/~/g;s/ 0$//g' | "${exe}"
else
    "${exe}" "${@}"
fi
