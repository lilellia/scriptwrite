from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from html.parser import HTMLParser
from io import StringIO
import os
from pathlib import Path
import re
import sys
from typing import Any, cast, NamedTuple, TypeVar

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import (
    QAction,
    QCloseEvent,
    QKeySequence,
    QTextBlock,
    QTextDocument,
    QTextFormat,
    QTextFragment,
)
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QWidget,
)

from scriptwrite import fs, parser, renderers

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


@dataclass(frozen=True, slots=True)
class _MenuItemData:
    name: str
    callback: Callable[[], None] | None
    shortcut: str | None = field(default=None, kw_only=True)


class _MenuBarProxy:
    def __init__(self, menubar: QMenuBar, *, menus: dict[str, Iterable[_MenuItemData]] | None = None) -> None:
        self._proxied = menubar
        self._menus: dict[str, QMenu] = {}

        if menus:
            self._add_menus(menus)

    def _add_menus(self, menus: dict[str, Iterable[_MenuItemData]]) -> None:
        for name, items in menus.items():
            self._add_menu(name, items)

    def _add_menu(self, name: str, items: Iterable[_MenuItemData]) -> None:
        menu = cast(QMenu, self._proxied.addMenu(name))

        for item in items:
            if item.name == "---":
                menu.addSeparator()
                continue

            action = QAction(item.name, menu)

            if item.callback is not None:
                action.triggered.connect(item.callback)

            if item.shortcut:
                action.setShortcut(QKeySequence(item.shortcut))

            menu.addAction(action)

        self._menus[name] = menu

    def __getattr__(self, key: Any) -> Any:
        return getattr(self._proxied, key)


class _HTMLInjector(HTMLParser):
    def __init__(self, buffer: StringIO) -> None:
        super().__init__()
        self._buffer = buffer

    @staticmethod
    def _make_attr_str(attrs: list[tuple[str, str | None]]) -> str:
        return "".join(f' {k}="{v}"' if v is not None else f" {k}" for k, v in attrs)

    def _inject(self, attrs: list[tuple[str, str | None]]) -> None:
        for k, v in attrs:
            if k.startswith("data-") and v is not None:
                # forcibly inject an anchor tag
                self._buffer.write(f'<a name="{k}_eq_{v}"></a>')

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._buffer.write(f"<{tag}{self._make_attr_str(attrs)}>")
        self._inject(attrs)

    @override
    def handle_endtag(self, tag: str) -> None:
        self._buffer.write(f"</{tag}>")

    @override
    def handle_data(self, data: str) -> None:
        self._buffer.write(data)

    @override
    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._buffer.write(f"<{tag}{self._make_attr_str(attrs)} />")
        self._inject(attrs)  # best we can do is just put the injected elements immediately after

    @override
    def handle_decl(self, decl: str) -> None:
        self._buffer.write(f"<!{decl}>")

    @override
    def handle_pi(self, data: str) -> None:
        self._buffer.write(f"<?{data}>")

    @classmethod
    def inject_into(cls, source: str) -> str:
        buffer = StringIO()
        instance = cls(buffer)
        instance.feed(source)
        return buffer.getvalue()


class CursorPosition(NamedTuple):
    line: int
    column: int


class TextEdit(QTextEdit):
    @property
    def content(self) -> str:
        return super().toPlainText()

    @content.setter
    def content(self, s: str, /) -> None:
        super().setPlainText(s)

    @property
    def html(self) -> str:
        return super().toHtml()

    @html.setter
    def html(self, s: str, /) -> None:
        # bring Qt kicking and screaming into the slightly-less-distant past
        s = _HTMLInjector.inject_into(s)
        super().setHtml(s)

    @property
    def doc(self) -> QTextDocument:
        return cast(QTextDocument, super().document())

    @property
    def cursor_position(self) -> CursorPosition:
        cur = super().textCursor()
        return CursorPosition(line=cur.blockNumber() + 1, column=cur.columnNumber() + 1)

    @property
    def font_size(self) -> int | None:
        """Return the editor's font size, in pt. If the system is using pixel sizing, return None."""
        if (size := super().font().pointSize()) <= 0:
            return None

        return size

    @contextmanager
    def suppress_signals(self) -> Iterator[None]:
        try:
            super().blockSignals(True)
            yield
        finally:
            super().blockSignals(False)


class EditorPane(TextEdit):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        super().setAcceptRichText(False)


class PreviewPane(TextEdit):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        super().setReadOnly(True)
        self.css = renderers.html.DEFAULT_CSS

    def scroll_to_line(self, line: int) -> None:
        def _blocks_of(document: QTextDocument) -> Iterator[QTextBlock]:
            curr = document.begin()
            while curr.isValid():
                yield curr
                curr = curr.next()

        def _fragments_of(block: QTextBlock) -> Iterator[QTextFragment]:
            it = block.begin()
            while not it.atEnd():
                yield it.fragment()
                it += 1

        def _valid_anchors() -> Iterator[str]:
            for block in _blocks_of(self.doc):
                for fragment in _fragments_of(block):
                    if (fmt := fragment.charFormat()).isAnchor():
                        if name := fmt.property(QTextFormat.Property.AnchorName):
                            yield from name

        def line_extractor(name: str) -> int:
            if match := re.match(r"data-source-line_eq_(\d+)", name):
                return int(match.group(1))

            return 0

        anchors = (name for name in _valid_anchors() if "data-source-line" in name)
        anchors = (name for name in anchors if line_extractor(name) <= line)
        try:
            anchor = max(anchors, key=line_extractor)
        except ValueError:
            pass
        else:
            super().scrollToAnchor(anchor)

    @property
    def css(self) -> str:
        return self.doc.defaultStyleSheet()

    @css.setter
    def css(self, s: str, /) -> None:
        # QTextEdit doesn't support all of modern CSS
        # so we'll modify what we need to in order to get a reasonable translation
        _FLOAT_REGEX = "[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)"
        base_font_size = self.font_size or 10  # use 10pt as a default fo rmeasurement

        def _em_to_px(em: float) -> int:
            # 1 em     S pt     4 px
            #       x ------ x ------
            #          1 em     3 pt
            #
            # where S is the font-size (pt). Thus, 1em = 4S/3 px.
            return round(em * 4 * base_font_size / 3)

        # QTextEdit does not support ch as a unit, so we'll convert it to pt
        def _convert_ch(m: re.Match[str]) -> str:
            em = 0.5 * float(m.group(1))  # 1ch = 0.5em
            return f"{_em_to_px(em)}px"

        s = re.sub(rf"({_FLOAT_REGEX})\s*ch", _convert_ch, s)

        # QTextEdit also does not support em as a font size, so we'll fix that too

        def _font_size_em_to_px(m: re.Match[str]) -> str:
            em = float(m.group(1))
            return f"font-size: {_em_to_px(em)}px;"

        s = re.sub(rf"font-size:\s*({_FLOAT_REGEX})\s*em\s*;", _font_size_em_to_px, s)

        cast(QTextDocument, super().document()).setDefaultStyleSheet(s)


class Label(QLabel):
    @property
    def content(self) -> str:
        return super().text()

    @content.setter
    def content(self, s: str, /) -> None:
        super().setText(s)


class StatusBar(QStatusBar):
    def __init__(self, parent: QWidget | None = None, *args: Any, **kwargs: Any) -> None:
        super().__init__(parent, *args, **kwargs)
        self.widgets: dict[str, Label] = {}

    def add_label(self, name: str, initial_text: str | None = None) -> Label:
        widget = Label(initial_text)
        super().addPermanentWidget(widget)
        self.widgets[name] = widget
        return widget

    def __getitem__(self, key: str) -> Label:
        return self.widgets[key]

    def ephemeral(self, message: str, duration: int = 2500) -> None:
        super().showMessage(message, duration)


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

    def _scroll_sync(self) -> None:
        line, col = self._editor.cursor_position

        self._status_bar["cursor"].content = f"L{line}:C{col}"

        if line == self._cached_editor_line_number:
            return

        self._preview.scroll_to_line(line)

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
        match QMessageBox.warning(self, "Unsaved Changes", text=message, buttons=buttons):
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

        self._status_bar["word-counts"].content = f"[Word Counts] {script.word_count_display}"

    def run(self) -> None:
        super().show()
        sys.exit(_app.exec())
