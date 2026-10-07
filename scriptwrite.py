from argparse import ArgumentParser
from pathlib import Path

from scriptwrite import LiveEditor, app
from scriptwrite.renderers.export import export_from_path


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", help="path to file to open on launch")
    parser.add_argument("-e", "--export", type=Path, metavar="TARGET", help="the target file to export to")
    args = parser.parse_args()

    if args.export:
        if not args.path:
            parser.error("-e/--export TARGET requires a source path")

        export_from_path(source=args.path, target=args.export, config=app.config.export)
        return

    LiveEditor(path=args.path).run()


if __name__ == "__main__":
    main()
