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


@dataclass(slots=True, frozen=True)
class AppDirs:
    config: Path
    data: Path
    logs: Path

    def __post_init__(self) -> None:
        self.config.mkdir(exist_ok=True)
        self.data.mkdir(exist_ok=True)
        self.logs.mkdir(exist_ok=True)

    @classmethod
    def get(cls, app_name: str = "scriptwrite") -> Self:
        HOME = Path.home()

        match sys.platform:
            case "win32":
                # config = %APPDATA%\scriptwrite
                config = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming")) / app_name

                # data = %LOCALAPPDATA%\AppData\Local/scriptwrite
                data = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local")) / app_name

                # logs
                logs = data / "Logs"

            case "darwin":
                support = HOME / "Library/Application Support" / app_name

                config = support
                data = support

                # logs have their own place
                # $HOME/Library/Logs/scriptwrite
                logs = HOME / "Library/Logs" / app_name

            case "linux":
                # config = $XDG_CONFIG_HOME/scriptwrite (default: ~/.config/scriptwrite)
                config = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / app_name

                # data = $XDG_DATA_DIR/scriptwrite (default: ~/.local/share/scriptwrite)
                data = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / app_name

                # logs = $XDG_STATE_DIR/scriptwrite (default: ~/.local/state/scriptwrite)
                logs = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state")) / app_name

            case unknown:
                raise ValueError(f"Unknown platform: {unknown!r}")

        return cls(config=config, data=data, logs=logs)


APP_DIRS = AppDirs.get()
