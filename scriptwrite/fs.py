from collections.abc import Iterable
from pathlib import Path
import shutil
import tempfile

from PyQt6.QtWidgets import QFileDialog, QWidget


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

    filename, _ = QFileDialog.getOpenFileName(
        QWidget(), caption=caption, directory=str(directory), filter=";;".join(filters)
    )

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

    filename, _ = QFileDialog.getSaveFileName(
        QWidget(), caption=caption, directory=str(directory), filter=";;".join(filters)
    )

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
