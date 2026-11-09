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

case "${1:-}" in
    compare) exec python3 -X utf8 -m scripts.compare_npm ;;
    test) exec python3 -X utf8 -m unittest discover -s tests -v ;;
    view) exec python3 -m http.server 8000 --bind 127.0.0.1 --directory out ;;
esac

if [ "${1:-}" = demo ]; then
    for example in is-even is-odd escape-string-regexp; do
        run --stage 5 --config "examples/$example.csv"
    done
    exit 0
fi

exec python3 -X utf8 -m src.depviz "$@"
