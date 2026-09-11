#!/usr/bin/env bash

# Test solver images sequentially and remove each image after its tests.

set -uo pipefail

usage() {
    cat <<'EOF'
Usage: tools/test-all-images.sh [--dry-run] [satex list options] [pattern]

By default, tests every solver marked "ok". Arguments other than --dry-run
are passed to "satex list", so a year, pattern, track, or status can be
selected before starting the run.

Examples:
  tools/test-all-images.sh
  tools/test-all-images.sh '*:2019'
  tools/test-all-images.sh --track main
  tools/test-all-images.sh --dry-run '*:2019'

Each satex image is removed after its test, whether the test passes or fails.
Shared Docker layers and unrelated images are left untouched.
EOF
}

dry_run=false
list_args=()
for argument in "$@"; do
    case "$argument" in
        -h|--help)
            usage
            exit 0
            ;;
        --dry-run)
            dry_run=true
            ;;
        *)
            list_args+=("$argument")
            ;;
    esac
done

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repository_dir=$(cd -- "$script_dir/.." && pwd)
cd "$repository_dir" || exit 1

image_list=$(mktemp "${TMPDIR:-/tmp}/satex-images.XXXXXX")
current_image=""

cleanup_current_image() {
    if [[ -n "$current_image" ]]; then
        docker image rm -f "satex/$current_image" >/dev/null 2>&1 || true
        current_image=""
    fi
}

cleanup() {
    cleanup_current_image
    rm -f "$image_list"
}

trap cleanup EXIT
trap 'exit 130' HUP INT TERM

if ! python3 satex.py list "${list_args[@]}" >"$image_list"; then
    echo "Unable to obtain the solver list." >&2
    exit 1
fi

total=$(wc -l <"$image_list" | tr -d ' ')
if [[ "$total" -eq 0 ]]; then
    echo "No matching solver image."
    exit 0
fi

if [[ "$dry_run" == true ]]; then
    echo "$total image(s) would be tested and removed:"
    sed 's/^/  /' "$image_list"
    exit 0
fi

passed=0
failed=()
cleanup_failed=()
index=0

while IFS= read -r image; do
    [[ -z "$image" ]] && continue
    index=$((index + 1))
    current_image="$image"

    printf '\n[%d/%d] Testing %s\n' "$index" "$total" "$image"
    if python3 satex.py test "$image"; then
        passed=$((passed + 1))
    else
        failed+=("$image")
    fi

    echo "Removing satex/$image"
    if docker image rm -f "satex/$image" >/dev/null; then
        current_image=""
    else
        cleanup_failed+=("$image")
        current_image=""
    fi
done <"$image_list"

printf '\nSummary: %d passed, %d failed, %d removal failures.\n' \
    "$passed" "${#failed[@]}" "${#cleanup_failed[@]}"

if ((${#failed[@]})); then
    echo "Failed tests:"
    printf '  %s\n' "${failed[@]}"
fi

if ((${#cleanup_failed[@]})); then
    echo "Images that could not be removed:"
    printf '  satex/%s\n' "${cleanup_failed[@]}"
fi

if ((${#failed[@]} || ${#cleanup_failed[@]})); then
    exit 1
fi
