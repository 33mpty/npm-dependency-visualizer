#!/bin/sh
set -eu
cd "$(dirname "$0")"

run() {
    python3 -X utf8 -m src.depviz "$@"
}

if [ "${1:-}" = errors ]; then
    for config in examples/invalid/*.csv; do
        printf '\n%s\n' "$config"
        if run --config "$config"; then
            printf 'Expected a configuration error\n' >&2
            exit 1
        else
            status=$?
            if [ "$status" -ne 2 ]; then
                exit "$status"
            fi
        fi
    done
    exit 0
fi

if [ "${1:-}" = test ]; then
    exec python3 -X utf8 -m unittest discover -s tests -v
fi

if [ "${1:-}" = demo ]; then
    for example in cycle diamond isolated; do
        run --stage 3 --config "examples/$example.csv"
    done
    exit 0
fi

exec python3 -X utf8 -m src.depviz "$@"
