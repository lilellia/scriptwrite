from argparse import ArgumentParser
import os
from pathlib import Path
import sys

from scriptwrite import LiveEditor


def _extend_qt6_plugin_paths() -> None:
    if not sys.platform.startswith("linux"):
        return

    os.environ.pop("QT_QPA_PLATFORMTHEME", None)

    # try to find the system-wide plugins
    system_paths = ["/usr/lib/qt6/plugins", "/usr/lib64/qt6/plugins", "/usr/lib/x86_64-linux-gnu/qt6/plugins"]
    system_paths = [p for p in system_paths if Path(p).exists()]

    if system_paths:
        os.environ.setdefault("QT_IM_MODULE", "fcitx")

        # add the system-wide plugins to the plugin search space
        extension = ":".join(system_paths)
        os.environ["QT_PLUGIN_PATH"] = f"{os.environ.get('QT_PLUGIN_PATH', '')}:{extension}".lstrip(":")


_extend_qt6_plugin_paths()


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("path", type=Path, help="path to file to open on launch")
    args = parser.parse_args()

    LiveEditor(path=args.path).run()


if __name__ == "__main__":
    main()
