from collections.abc import Callable, Iterable
import os
from pathlib import Path
import sys
import textwrap
from typing import cast, TypeVar

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QSplitter,
    QWidget,
)

from scriptwrite import fs, parser, renderers
from scriptwrite.widgets import _MenuBarProxy, _MenuItemData, EditorPane, PreviewPane, SourceLineData, StatusBar

Q = TypeVar("Q", bound=QWidget)


def _extend_qt6_plugin_paths() -> None:
    if not sys.platform.startswith("linux"):
        return

    # try to find the system-wide plugins
    system_paths = ["/usr/lib/qt6/plugins", "/usr/lib64/qt6/plugins", "/usr/lib/x86_64-linux-gnu/qt6/plugins"]
    system_paths = [p for p in system_paths if Path(p).exists()]

    if system_paths:
        os.environ.setdefault("QT_IM_MODULE", "fcitx")

        # add the system-wide plugins to the plugin search space
        extension = ":".join(system_paths)
        os.environ["QT_PLUGIN_PATH"] = f"{os.environ.get('QT_PLUGIN_PATH', '')}:{extension}".lstrip(":")


_extend_qt6_plugin_paths()

_app = QApplication(["scriptwrite"])


class LiveEditor(QMainWindow):
    def __init__(self, path: Path | None = None, *, title: str = "scriptwrite") -> None:
        super().__init__()
        self.title = title

        self._split = QSplitter()
        super().setCentralWidget(self._split)

        self._editor = self.add_pane(EditorPane())
        self._preview = self.add_pane(PreviewPane())
        self._editor.textChanged.connect(self._on_change)

        self._cached_editor_line_number = 0
        self._editor.cursorPositionChanged.connect(self._scroll_sync)
        self._preview.cursorPositionChanged.connect(self._reverse_scroll_sync)

        self._menubar = self._init_menu()
        self._status_bar = self._init_status_bar()

        self._filepath: Path | None = None
        if path:
            self._open_file(path)

        self._dirty: bool = False

        self._render_timer = self._init_timer(duration=200, callback=self._compile)

    @property
    def title(self) -> str:
        return super().windowTitle()

    @title.setter
    def title(self, value: str, /) -> None:
        super().setWindowTitle(str(value))

    @property
    def dirty(self) -> bool:
        return self._dirty

    @dirty.setter
    def dirty(self, val: bool, /) -> None:
        self._dirty = bool(val)
        symbol = "*" if self._dirty else "-"
        self.title = f"scriptwrite {symbol} {self._filepath or 'untitled'}"

    def add_pane(self, widget: Q) -> Q:
        """Add the given widget as an application pane."""
        self._split.addWidget(widget)
        return widget

    def _init_menu(self) -> _MenuBarProxy:
        menus: dict[str, Iterable[_MenuItemData]] = {
            "&File": [
                _MenuItemData("&New", self._new_file, shortcut="Ctrl+n"),
                _MenuItemData("&Open", self._get_open_file, shortcut="Ctrl+o"),
                _MenuItemData("&Save", self._save_file, shortcut="Ctrl+s"),
                _MenuItemData("---", None),
                _MenuItemData("&Quit", self._quit, shortcut="Ctrl+q"),
            ],
            "&Edit": [
                _MenuItemData("&Undo", self._editor.undo, shortcut="Ctrl+z"),
                _MenuItemData("&Redo", self._editor.redo, shortcut="Ctrl+Shift+z"),
                _MenuItemData("---", None),
                _MenuItemData("&Cut", self._editor.cut, shortcut="Ctrl+x"),
                _MenuItemData("&Copy", self._editor.copy, shortcut="Ctrl+c"),
                _MenuItemData("&Paste", self._editor.paste, shortcut="Ctrl+v"),
                _MenuItemData("---", None),
                _MenuItemData("&Find", self._find, shortcut="Ctrl+f"),
                _MenuItemData("&Replace", self._replace, shortcut="Ctrl+h"),
            ],
            "&Help": [
                _MenuItemData("&Help", self._show_help, shortcut="Ctrl+Shift+/"),
                _MenuItemData("&About", self._show_about),
            ],
        }

        return _MenuBarProxy(cast(QMenuBar, super().menuBar()), menus=menus)

    def _init_timer(self, duration: int, callback: Callable[[], None]) -> QTimer:
        timer = QTimer()
        timer.setSingleShot(True)
        timer.setInterval(duration)
        timer.timeout.connect(callback)
        return timer

    def _init_status_bar(self) -> StatusBar:
        bar = StatusBar(self)
        bar.add_label("word-counts")
        bar.add_label("cursor", "L1:C1")
        super().setStatusBar(bar)
        return bar

    def _scroll_sync(self, *, force: bool = False) -> None:
        line, col = self._editor.cursor_position

        self._status_bar["cursor"].content = f"L{line}:C{col}"

        if line == self._cached_editor_line_number and not force:
            return

        with self._preview.suppress_signals():
            self._preview.scroll_to_source_line(line)

    def _reverse_scroll_sync(self, *, force: bool = False) -> None:
        line, _ = self._preview.cursor_position
        block = self._preview.doc.findBlockByLineNumber(line - 1)

        if (data := block.userData()) and isinstance(data, SourceLineData):
            # move the cursor to the start of the corresponding line
            target = self._editor.doc.findBlockByLineNumber(data.source_line - 1)
            with self._editor.suppress_signals():
                self._editor.scroll_to_block(target, align_top=True)
        else:
            # the block probably should have had data but didn't, so... :shrug:
            self._status_bar.ephemeral("Scroll sync failure: no source line data found", 1000)

    def _new_file(self) -> None:
        """Create a new file in the editor. If the current document has changed, prompt save."""
        if not self._maybe_save():
            return

        self._filepath = None
        self._editor.content = ""
        self.dirty = False

    def _open_file(self, path: Path) -> None:
        """Open the given file, dumping its contents into the editor pane."""
        self._filepath = path

        with self._editor.suppress_signals():
            self._editor.content = path.read_text()

        self.dirty = False
        self._compile()
        with open("/tmp/x.html", "w") as f:
            f.write(self._preview.html)

        self._status_bar.ephemeral(f"Loaded: {path}")

    def _get_open_file(self) -> None:
        """Query the user for the path to open. If the current document has changed, ask them to save."""
        if not self._maybe_save():
            return

        if (path := fs.get_open_filepath(filters=["Markdown Files (*.md)", "All Files (*)"])) is None:
            return

        self._open_file(path)

    def _maybe_save(self) -> bool:
        """Prompt the user to save if changes has been made.
        Returns True if it is safe to continue, False otherwise.
        """
        if not self.dirty:
            return True

        message = f"The script {self._filepath or 'untitled'} has been modified.\nWould you like to save your changes?"
        buttons = (
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
        )
        match QMessageBox.warning(self, "Unsaved Changes", message, buttons=buttons):
            case QMessageBox.StandardButton.Save:
                self._save_file()
                return not self.dirty  # True if save succeeded, False otherwise

            case QMessageBox.StandardButton.Cancel:
                # aborted, so not safe to proceed
                self._status_bar.ephemeral("Save aborted")
                return False

            case QMessageBox.StandardButton.Discard:
                # changes discarded, carry on
                self._status_bar.ephemeral("Unsaved changes discarded")
                return True

        return False

    def _save_file(self) -> None:
        """Save the content of the editor pane to file."""
        if self._filepath is None:
            if (path := fs.get_save_filepath(filters=["Markdown Files (*.md)", "All Files (*)"])) is None:
                return

            self._filepath = path

        try:
            fs.atomic_write(self._editor.content, self._filepath)
            self._status_bar.ephemeral(f"Saved to {self._filepath}")
        except Exception as e:
            self._status_bar.ephemeral(f"Save failed: {e}")

        self.dirty = False

    def _quit(self) -> None:
        """Exit the application."""
        # QMainWindow.close returns bool for some reason, so we wrap it here to make it return None
        super().close()

    @override
    def closeEvent(self, event: QCloseEvent | None) -> None:
        if self._maybe_save():
            if event:
                event.accept()
        else:
            if event:
                event.ignore()

    def _find(self) -> None:
        # TODO
        pass

    def _replace(self) -> None:
        # TODO
        pass

    def _on_change(self) -> None:
        """Called when the editor pane's content changes. Registers the update for the preview pane."""
        self.dirty = True
        self._render_timer.start()  # debounce

    def _compile(self) -> None:
        """Update the content of the preview pane."""
        script = parser.parse_text(self._editor.content)
        content = renderers.html.render_html(script, inject_css=False)
        self._preview.html = content
        self._scroll_sync(force=True)

        self._status_bar["word-counts"].content = f"[Word Counts] {script.word_count_display}"

    def _show_help(self) -> None:
        message = textwrap.dedent("""
            T: This is a line of dialogue spoken by the T character.

            This is also spoken by T.

            R: This is spoken by R.

            --Lead a line with two hyphens to assign it to the listener.

            (inline direction) Also by R, with *emphasis*.

            ++Lead a line with two plus signs to mark it as a stage direction.

        """)
        QMessageBox.information(None, "Help", message)

    def _show_about(self) -> None:
        QMessageBox.information(None, "About scriptwrite", "scriptwrite v0.1.0\nⓒ 2026 lilellia")

    def run(self) -> None:
        super().showMaximized()
        sys.exit(_app.exec())
