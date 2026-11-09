import argparse
import sys
from dataclasses import asdict
from pathlib import Path

from .config import ProjectError, read_config


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Практическая № 2, вариант 3"
    )
    parser.add_argument(
        "--config", type=Path, default=Path("examples/is-odd.csv")
    )
    return parser.parse_args()


def show_config(config):
    for key, value in asdict(config).items():
        display = str(value).lower() if isinstance(value, bool) else value
        print(f"{key}={display}")


def main():
    args = parse_arguments()
    try:
        config = read_config(args.config)
        show_config(config)
    except ProjectError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
