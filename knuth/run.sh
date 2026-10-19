#!/bin/bash
# Knuth's programs read their own format and answer in it: the satisfying
# assignment as literals where ~ marks a negation, then "!SAT!", or "UNSAT" on
# unsatisfiable formulas, and they always exit 0.  In --satex mode the
# instance is translated on the way in and the answer on the way out, so the
# images speak the competition format like every other solver here.
exe="${0}.out"
if [[ "${1}" == "--satex" ]]; then
    shift
    out=$(mktemp /tmp/knuth.XXXXXX)
    grep -v "^[cp]" "${1}" | sed 's/-/~/g;s/ 0$//g' | "${exe}" > "${out}" 2>&1
    if grep -qE '^UNSAT' "${out}"; then
        echo "s UNSATISFIABLE"
        rm -f "${out}"
        exit 20
    fi
    if grep -q '!SAT!' "${out}"; then
        echo "s SATISFIABLE"
        grep -hoE '^ *~?[0-9]+( +~?[0-9]+)* *$' "${out}" | tr -s ' \n' ' ' |
            sed 's/~/-/g; s/^ *//; s/ *$//; s/^/v /; s/$/ 0/'
        rm -f "${out}"
        exit 10
    fi
    cat "${out}"
    rm -f "${out}"
    exit 0
else
    "${exe}" "${@}"
fi
