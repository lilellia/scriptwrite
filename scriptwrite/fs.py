from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Self

from PySide6.QtWidgets import QFileDialog, QWidget


def get_open_filepath(
    directory: Path | None = None, *, caption: str | None = None, filters: Iterable[str] | None = None
) -> Path | None:
    """Prompt the user for a filename to open.

    If filters is provided, it should be of the form:
    filters=["Images (*.png *.xpm *.jpg)", "All Files (*)"]
    """
    if directory is None:
        directory = Path.home()

    if caption is None:
        caption = "Open File"

    if filters is None:
        filters = ["All Files (*)"]

    filename, _ = QFileDialog.getOpenFileName(QWidget(), caption=caption, dir=str(directory), filter=";;".join(filters))

    return Path(filename) if filename else None


def get_save_filepath(
    directory: Path | None = None, *, caption: str | None = None, filters: Iterable[str] | None = None
) -> Path | None:
    """Prompt the user for a filename to save to.

    If filters is provided, it should be of the form:
    filters=["Images (*.png *.xpm *.jpg)", "All Files (*)"]
    """
    if directory is None:
        directory = Path.home()

    if caption is None:
        caption = "Save File"

    if filters is None:
        filters = ["All Files (*)"]

    filename, _ = QFileDialog.getSaveFileName(QWidget(), caption=caption, dir=str(directory), filter=";;".join(filters))

    return Path(filename) if filename else None


def atomic_write(content: str, path: Path) -> None:
    """Perform an atomic write of the given content to the given path."""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
        f.write(content)

    try:
        shutil.move(f.name, path)
    except Exception:
        Path(f.name).unlink(missing_ok=True)
        raise


def mkdir_p(path: Path, mode: int = 0o777) -> None:
    """Create the given directory and its parents as needed, with the given mode.
    If the path already exists, this is a no-op, even if the path points to a file.
    """
    if path.exists():
        if not path.is_dir():
            raise NotADirectoryError(path)

        return

    parts = deque(path.resolve().parts)
    curr = Path(parts.popleft())

    while True:
        if not curr.exists():
            # pathlib.Path.mkdir(mode) specifically has the incorrect behaviour, always using 0o777 for parents,
            # regardless of what the passed mode is, which... why are you taking the mode as a parameter then!? :hmph:
            # (Apparently, it's `mkdir -p`'s fault, but I'd argue that's worse since `mkdir -p` should get it right.)
            curr.mkdir(mode=mode)

        if parts:
            curr /= parts.popleft()
        else:
            return


@dataclass(slots=True, frozen=True)
class AppDirs:
    config: Path
    data: Path
    logs: Path
    autosaves: Path

    def __post_init__(self) -> None:
        # "If, when attempting to write a file, the destination directory is non-existent an attempt should be made
        # to create it with permission 0700. If the destination directory exists already the permissions should not
        # be changed. [XDG spec]"
        #
        # And... uh... Windows and macOS users can just deal with that. 0o700 seems semantically correct anyway.
        mode = 0o700

        mkdir_p(self.config, mode=mode)
        mkdir_p(self.data, mode=mode)
        mkdir_p(self.logs, mode=mode)
        mkdir_p(self.autosaves, mode=mode)

    @staticmethod
    def _get_xdg_base(key: str, fallback: Path) -> Path:
        """Resolve XDG_$key_HOME (e.g. $XDG_CONFIG_HOME) or the fallback."""
        envvar = f"XDG_{key.upper()}_HOME"
        if value := os.environ.get(envvar):
            if (path := Path(value)).is_absolute():
                # The XDG spec specifies that these paths must be absolute.
                # "If an implementation encounters a relative path in any of these variables it should
                #  consider the path invalid and ignore it."
                return path
            else:
                # We're in the process of determining the log directory, so the best we can do is write to stderr
                # and... hope that the user is running this GUI application via a terminal? :shrug:
                sys.stderr.write(f"${envvar} found to be relative path {path}. This is invalid and will be ignored.\n")

        return fallback

    @classmethod
    def get(cls, app_name: str = "scriptwrite") -> Self:
        HOME = Path.home()

        match sys.platform:
            case "win32":
                # base directories - these do include the .../app_name subdir baked in
                appdata = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming")) / app_name
                local_appdata = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local")) / app_name

                config = appdata
                data = local_appdata
                logs = local_appdata / "Logs"
                autosaves = local_appdata / "Autosaves"

            case "darwin":
                support = HOME / "Library/Application Support" / app_name

                config = support
                data = support
                autosaves = support / "Autosaves"

                # logs have their own place
                # $HOME/Library/Logs/scriptwrite
                logs = HOME / "Library/Logs" / app_name

            case "linux":
                # XDG base directories (underscore used in place of dot because ".config" is not a valid identifier)
                # these do include the .../app_name subdir baked in
                _config = cls._get_xdg_base("CONFIG", HOME / ".config") / app_name
                _share = cls._get_xdg_base("DATA", HOME / ".local/share") / app_name
                _state = cls._get_xdg_base("STATE", HOME / ".local/state") / app_name

                # concrete placements
                config = _config
                data = _share
                logs = _state / "logs"
                autosaves = _state / "autosaves"

            case unknown:
                raise ValueError(f"Unknown platform: {unknown!r}")

        return cls(config=config, data=data, logs=logs, autosaves=autosaves)


APP_DIRS = AppDirs.get()
