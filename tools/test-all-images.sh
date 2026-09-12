#!/usr/bin/env bash

# Test solver images sequentially and remove each image after its tests.

set -uo pipefail

usage() {
    cat <<'EOF'
Usage: tools/test-all-images.sh [options] [satex list options] [pattern]

By default, tests every solver marked "ok" using its published image. Arguments
not recognized below are passed to "satex list", so a year, pattern, track, or
status can be selected before starting the run.

Options:
  --build          Build each solver from its archived sources before testing.
  --no-cache       With --build, disable the Docker build cache.
  --dry-run        Print the selected images without building or testing.
  --log-dir DIR    Store detailed build/error logs in DIR.
  -h, --help       Show this help.

Examples:
  tools/test-all-images.sh
  tools/test-all-images.sh --build '*:2019'
  tools/test-all-images.sh '*:2019'
  tools/test-all-images.sh --track main
  tools/test-all-images.sh --dry-run '*:2019'

Each satex image is removed after its test, whether the test passes or fails.
Shared Docker layers and unrelated images are left untouched.
EOF
}

dry_run=false
build_sources=false
no_cache=false
log_dir=""
list_args=()
while (($#)); do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        --dry-run)
            dry_run=true
            shift
            ;;
        --build)
            build_sources=true
            shift
            ;;
        --no-cache)
            no_cache=true
            shift
            ;;
        --log-dir)
            if (($# < 2)); then
                echo "--log-dir requires a directory." >&2
                exit 2
            fi
            log_dir=$2
            shift 2
            ;;
        --log-dir=*)
            log_dir=${1#*=}
            shift
            ;;
        --)
            shift
            list_args+=("$@")
            break
            ;;
        *)
            list_args+=("$1")
            shift
            ;;
    esac
done

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repository_dir=$(cd -- "$script_dir/.." && pwd)
cd "$repository_dir" || exit 1

image_list=$(mktemp "${TMPDIR:-/tmp}/satex-images.XXXXXX")
current_image=""

report() {
    local status=$1 image=$2 test_name=$3 detail=${4:-}
    if [[ -n "$detail" ]]; then
        printf '%-4s %-35s %s (%s)\n' "$status" "$image" "$test_name" "$detail"
    else
        printf '%-4s %-35s %s\n' "$status" "$image" "$test_name"
    fi
}

cleanup_current_image() {
    if [[ -n "$current_image" ]]; then
        remove_image_if_present "satex/$current_image" || true
        remove_image_if_present "satex/builder-$current_image" || true
        remove_image_if_present "satex/stage-source-extract-$current_image" || true
        remove_image_if_present "satex/stage-build-environment-$current_image" || true
        remove_image_if_present "satex/stage-runtime-dependencies-$current_image" || true
        current_image=""
    fi
}

remove_image_if_present() {
    local image=$1
    if ! docker image inspect "$image" >/dev/null 2>&1; then
        return 0
    fi
    docker image rm -f "$image" >/dev/null 2>&1
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
    action="tested"
    [[ "$build_sources" == true ]] && action="built and tested"
    echo "$total image(s) would be $action and removed:"
    sed 's/^/  /' "$image_list"
    exit 0
fi

passed=0
failed=()
cleanup_failed=()
index=0

if [[ -z "$log_dir" ]]; then
    run_id=$(date -u +%Y%m%dT%H%M%SZ)
    log_dir="$repository_dir/test-results/$run_id"
fi
mkdir -p "$log_dir"

while IFS= read -r image; do
    [[ -z "$image" ]] && continue
    index=$((index + 1))
    current_image="$image"

    report "info" "$image" "progress" "$index/$total"
    safe_name=${image//[:\/]/-}
    build_log="$log_dir/$safe_name-build.log"
    build_status="$log_dir/$safe_name-build.jsonl"
    test_log="$log_dir/$safe_name-test.log"

    build_ok=true
    if [[ "$build_sources" == true ]]; then
        build_command=(python3 satex.py build --terse --status-file "$build_status")
        [[ "$no_cache" == true ]] && build_command+=(--no-cache)
        if ! "${build_command[@]}" "$image" 2>"$build_log"; then
            if ! grep -q '"status": "fail"' "$build_status" 2>/dev/null; then
                report "fail" "$image" "build-unknown" "$build_log"
            fi
            build_ok=false
        fi
    else
        report "skip" "$image" "source-build" "not requested"
    fi

    test_ok=false
    if [[ "$build_ok" == true ]]; then
        if python3 satex.py test --terse "$image" 2>"$test_log"; then
            test_ok=true
        else
            report "fail" "$image" "test-suite" "$test_log"
        fi
    else
        report "skip" "$image" "test-suite" "build failed"
    fi

    if [[ "$test_ok" == true ]]; then
        passed=$((passed + 1))
    else
        failed+=("$image")
    fi

    removal_ok=true
    remove_image_if_present "satex/$image" || removal_ok=false
    remove_image_if_present "satex/builder-$image" || removal_ok=false
    if [[ "$removal_ok" == true ]]; then
        report "ok" "$image" "image-remove"
        current_image=""
    else
        report "fail" "$image" "image-remove"
        cleanup_failed+=("$image")
        current_image=""
    fi
done <"$image_list"

printf '\nSummary: %d passed, %d failed, %d removal failures. Logs: %s\n' \
    "$passed" "${#failed[@]}" "${#cleanup_failed[@]}" "$log_dir"

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
