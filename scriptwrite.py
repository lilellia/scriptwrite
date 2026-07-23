from argparse import ArgumentParser
from pathlib import Path

from scriptwrite import LiveEditor


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", help="path to file to open on launch")
    args = parser.parse_args()

    LiveEditor(path=args.path).run()


if __name__ == "__main__":
    main()
