from collections.abc import Iterator
from contextlib import contextmanager
import faulthandler
import os
from os import PathLike
from pathlib import Path
import sys
from typing import Any, assert_never, IO, Literal

from PySide6.QtCore import QCoreApplication, QFileSystemWatcher, QObject, Qt
from PySide6.QtGui import QPalette, QStyleHints
from PySide6.QtWidgets import QApplication, QStyle, QStyleFactory

from scriptwrite.fs import APP_DIRS
from scriptwrite.log import logger
from scriptwrite.types import F
from scriptwrite.widgets.signals import QtSignalProperty


class Application(QApplication):
    def __init__(self, *args: Any, mode: Literal["light", "dark", "system"] = "system", **kwargs: Any) -> None:
        self._crashfile = self._enable_crash_handler()

        if sys.platform.startswith("linux"):
            self._force_ime()
            self._extend_qt6_plugin_paths()

        super().__init__(*args, **kwargs)
        self.theme = "Fusion"
        self.mode = mode

    @property
    def style_hints(self) -> QStyleHints:
        return super().styleHints()

    @property
    def theme(self) -> QStyle:
        return super().style()

    @theme.setter
    def theme(self, value: str | QStyle, /) -> None:
        super().setStyle(value)

    @property
    def mode(self) -> Literal["light", "dark", "system"]:
        match super().styleHints().colorScheme():
            case Qt.ColorScheme.Light:
                return "light"
            case Qt.ColorScheme.Dark:
                return "dark"
            case _:
                return "system"

    @mode.setter
    def mode(self, value: Literal["light", "dark", "system"], /) -> None:
        match value:
            case "light":
                super().styleHints().setColorScheme(Qt.ColorScheme.Light)

                if sys.platform == "linux" and (fallback := QStyleFactory.create("windows")):
                    # prevent Linux from injecting its own dark mode
                    super().setPalette(fallback.standardPalette())

            case "dark":
                super().styleHints().setColorScheme(Qt.ColorScheme.Dark)
                super().setPalette(QPalette())
                super().setStyle(QStyleFactory.create("Fusion"))

            case "system":
                super().styleHints().setColorScheme(Qt.ColorScheme.Unknown)
                super().setPalette(QPalette())
                super().setStyle(QStyleFactory.create("Fusion"))

            case _:
                assert_never(value)

    def _enable_crash_handler(self) -> IO[str]:
        f = open(APP_DIRS.logs / "crash.log", "w+")

        if sys.version_info >= (3, 14):
            # option to dump the C stack trace was added in 3.14
            faulthandler.enable(file=f, all_threads=True, c_stack=True)
        else:
            faulthandler.enable(file=f, all_threads=True)

        return f

    @staticmethod
    def _force_ime() -> None:
        os.environ.setdefault("QT_IM_MODULE", "fcitx")

    @staticmethod
    def _extend_qt6_plugin_paths() -> None:
        pool = ["/usr/lib/qt6/plugins", "/usr/lib64/qt6/plugins", "/usr/lib/x86_64-linux-gnu/qt6/plugins"]

        for path in pool:
            if Path(path).exists():
                logger.info(f"Adding plugin path: {path}")
                QCoreApplication.addLibraryPath(path)


class FileWatcher(QFileSystemWatcher):
    _on_directory_change: QtSignalProperty = QtSignalProperty("directoryChanged")

    def __init__(
        self,
        path: str | PathLike[str],
        parent: QObject | None = None,
        *args: Any,
        on_change: F | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, *args, **kwargs)
        self._path = Path(path)

        try:
            self._mtime = self._path.stat().st_mtime
        except FileNotFoundError as e:
            raise ValueError(f"Cannot watch nonexistent file {path}") from e

        self.on_change = on_change
        self._on_directory_change = self.__on_directory_change__
        self.bind()

    @property
    def directory(self) -> Path:
        return self._path.parent

    def bind(self) -> None:
        if str(self.directory) not in super().directories() and self._path.exists():
            super().addPath(str(self.directory))

    @contextmanager
    def suppress_signals(self) -> Iterator[None]:
        super().blockSignals(True)
        try:
            yield
        finally:
            super().blockSignals(False)

    def __on_directory_change__(self) -> None:
        self.bind()

        try:
            mtime = self._path.stat().st_mtime
        except FileNotFoundError:
            # file was deleted
            # possibly an atomic write, in which case we should get another trigger on the write
            pass
        else:
            if mtime > self._mtime:
                self._mtime = mtime

                if self.on_change:
                    self.on_change()
