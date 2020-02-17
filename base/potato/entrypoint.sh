#!/usr/bin/env bash

DB=/solvers/solvers.json

set -e

if [ -z "${SOLVER}" ]; then
    echo "Oops, no SOLVER defined."
    exit 1
fi

get_param() {
    jq -r ".\"${SOLVER}\".$1" "${DB}"
}

SOLVER_CALL=$(get_param call)
SOLVER_NAME=$(get_param name)
SOLVER_PATH=$(get_param path)
if [[ "${SOLVER_PATH}" == "null" ]]; then
    SOLVER_PATH="${SOLVER_NAME}"
fi

usage() {
    echo "Usage:"
    echo "  FILECNF"
    echo "  --raw <$SOLVER arguments>"
    echo "  -h"
    exit 1
}

call_solver() {
    set -x
    "/solvers/${SOLVER_PATH}/${SOLVER_CALL}" "${@}"
}

mycall() {
    case $# in
        1) k=args ;;
        *) usage
    esac



    FILECNF="${1}"
    if [[ "${FILECNF##*.}" == "gz" ]]; then
        if [[ "$(get_param gz)" == "false" ]]; then
            echo "# gunzip ${FILECNF}..."
            gunzip -c "${FILECNF}" > /tmp/cnf
            echo "# ...done"
            FILECNF=/tmp/cnf
        fi
    fi
    FILECNF=${FILECNF/,/\\,}

    args=$(get_param $k|jq -r 'join(" ")'| sed "s,FILECNF,$FILECNF,g")
    call_solver ${args}
}

echo "#### $DOCKER_IMAGE ####"

if [ -z $1 ]; then
    usage
fi

case "${1:-}" in
    -h|--help) usage;;
    --raw) shift; call_solver "${@}";;
    *) mycall "${@}"
esac
