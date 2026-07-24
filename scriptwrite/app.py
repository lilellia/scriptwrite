from collections.abc import Iterable
from contextlib import suppress
from functools import partial
from pathlib import Path
import re
import sys
import textwrap
import tomllib
from typing import cast, Literal

from scriptwrite.log import logger
from scriptwrite.utils import discard, find_text, make_needle
from scriptwrite.widgets.actions import Shortcut
from scriptwrite.widgets.display import set_font_size

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtGui import QCloseEvent, QTextBlock
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSplitter,
)

from scriptwrite import fs, parser
from scriptwrite.config import Config
from scriptwrite.features import EditorPane, FindToolBar, PreviewPane
from scriptwrite.types import W
from scriptwrite.widgets import (
    Application,
    MenuBar,
    MenuItemData,
    StatusBar,
    Timer,
)

config = Config.load()
logger.info(f"Loaded {config=}")

_app = Application(["scriptwrite"], mode=config.mode)


class LiveEditor(QMainWindow):
    def __init__(self, path: Path | None = None, *, title: str = "scriptwrite") -> None:
        super().__init__()
        self.title = title

        self._split = QSplitter()
        super().setCentralWidget(self._split)

        self._editor = self.add_pane(EditorPane())
        self._preview = self.add_pane(PreviewPane())
        self._editor.on_change = self._on_change

        self._cached_editor_line_number = 0
        self._editor.on_cursor_move = self._scroll_sync
        self._preview.on_cursor_move = self._reverse_scroll_sync

        self._find_toolbar = FindToolBar(self, discard(self._find), self._replace).bind()

        self._menubar = self._init_menu()
        self._other_shortcuts = self._init_shortcuts()
        self._status_bar = self._init_status_bar()

        # font sizes
        self._font_sizes: dict[Literal["default", "current"], int] = {
            "default": config.font_size,
            "current": config.font_size,
        }
        self._change_font_size()
        self._dirty: bool = False

        self._filepath: Path | None = None
        if path:
            self._open_file(path)
        else:
            self._new_file()

        self._load_autosave()

        self._render_timer = Timer(duration=200, callback=self._compile)
        self._autosave_timer = Timer(duration=10000, callback=self._autosave)

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

    def add_pane(self, widget: W) -> W:
        """Add the given widget as an application pane."""
        self._split.addWidget(widget)
        return widget

    def _init_menu(self) -> MenuBar:

        menus: dict[str, Iterable[MenuItemData]] = {
            "&File": [
                MenuItemData("&New", self._new_file, shortcut="Ctrl+N"),
                MenuItemData("&Open", self._get_open_file, shortcut="Ctrl+O"),
                MenuItemData("&Save", self._save_file, shortcut="Ctrl+S"),
                MenuItemData("Save As", self._save_as, shortcut="Ctrl+Shift+S"),
                MenuItemData("---", None),
                MenuItemData("&Quit", self._quit, shortcut="Ctrl+Q"),
            ],
            "&Edit": [
                MenuItemData("&Undo", self._editor.undo, shortcut="Ctrl+Z"),
                MenuItemData("&Redo", self._editor.redo, shortcut=("Ctrl+Y", "Ctrl+Shift+Z")),
                MenuItemData("---", None),
                MenuItemData("&Cut", self._editor.cut, shortcut="Ctrl+X"),
                MenuItemData("&Copy", self._editor.copy, shortcut="Ctrl+C"),
                MenuItemData("&Paste", self._editor.paste, shortcut="Ctrl+V"),
                MenuItemData("---", None),
                MenuItemData("&Find/Replace", self._find_toolbar.toggle, shortcut=("Ctrl+F", "Ctrl+H")),
            ],
            "&Tools": [
                MenuItemData(
                    "&Insert Header Template",
                    self._insert_header,
                    shortcut=("Ctrl+Shift+H"),
                )
            ],
            "&Help": [
                MenuItemData("&Help", self._show_help, shortcut="Ctrl+?"),
                MenuItemData("&About", self._show_about),
            ],
        }

        return MenuBar(self, menus=menus)

    def _init_shortcuts(self) -> list[Shortcut]:
        return [
            # font size changes
            Shortcut("Ctrl++", self, callback=partial(self._change_font_size, direction=1)),
            Shortcut("Ctrl+-", self, callback=partial(self._change_font_size, direction=-1)),
            Shortcut("Ctrl+0", self, callback=partial(self._change_font_size, direction=0)),
        ]

    def _init_status_bar(self) -> StatusBar:
        bar = StatusBar(self)
        bar.add_label("word-counts")
        bar.add_label("cursor", "L1:C1")
        super().setStatusBar(bar)
        return bar

    def _scroll_sync(self, *, force: bool = False) -> None:
        line, col = self._editor._cursor.position

        self._status_bar["cursor"].content = f"L{line}:C{col}"

        if line == self._cached_editor_line_number and not force:
            return

        with self._preview.suppress_signals():
            self._preview.scroll_to_source_line(line)
            self._preview.highlight_current_block()

    def _reverse_scroll_sync(self, *, force: bool = False) -> None:
        if (source_line := self._preview.get_current_source_line()) is not None:
            target = cast(QTextBlock, self._editor.get_block_at_line(source_line))

            with self._editor.suppress_signals():
                self._editor.scroll_to_block(target, align=True)
                self._editor.highlight_current_block()
                self._editor.setFocus()

    def _new_file(self) -> None:
        """Create a new file in the editor. If the current document has changed, prompt save."""
        if not self._maybe_save():
            return

        self._filepath = None
        self._editor.content = ""
        self._insert_header()
        self.dirty = False

    def _open_file(self, path: Path) -> None:
        """Open the given file, dumping its contents into the editor pane."""
        self._filepath = path

        with self._editor.suppress_signals():
            self._editor.content = path.read_text()

        self.dirty = False
        self._compile()

        self._status_bar.ephemeral(f"Loaded: {path}")
        with self._editor.suppress_signals():
            self._editor._highlighter.rehighlight()

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

                # we'll also discard the autosave file
                with suppress(OSError):
                    self._get_autosave_dest().unlink()

                return True

        return False

    def _save_file(self, *, save_as: bool = False, directory: Path = Path.home()) -> None:
        """Save the content of the editor pane to file."""
        if self._filepath is None or save_as:
            if (path := fs.get_save_filepath(directory, filters=["Markdown Files (*.md)", "All Files (*)"])) is None:
                return

            self._filepath = path

        try:
            fs.atomic_write(self._editor.content, self._filepath)
            self._status_bar.ephemeral(f"Saved to {self._filepath}")
        except Exception as e:
            self._status_bar.ephemeral(f"Save failed: {e}")
        else:
            # remove autosave file
            with suppress(OSError):
                self._get_autosave_dest().unlink()

        self.dirty = False

    def _save_as(self) -> None:
        if self._filepath is None:
            self._save_file(save_as=True)
        else:
            self._save_file(save_as=True, directory=self._filepath.parent)

    def _get_autosave_dest(self) -> Path:
        filepath = self._filepath.name if self._filepath else "untitled1.md"
        return fs.APP_DIRS.autosaves / filepath

    def _autosave(self) -> None:
        """Perform an autosave for the current file."""
        if not self._dirty:
            return

        try:
            fs.atomic_write(self._editor.content, self._get_autosave_dest())
            self._status_bar.ephemeral("Autosave complete", duration=1000)
        except Exception as e:
            self._status_bar.ephemeral(f"Autosave failed: {e}")

    def _load_autosave(self) -> None:

        if not (autosaves := list(fs.APP_DIRS.autosaves.iterdir())):
            return

        buttons = QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Discard
        message = f"The editor appears to have closed unexpectedly. Would you like to reload autosave: {autosaves[0]}?"
        match QMessageBox.warning(self, "Detected Autosaves", message, buttons):
            case QMessageBox.StandardButton.Open:
                self._open_file(autosaves[0])
                self._filepath = None

            case QMessageBox.StandardButton.Discard:
                pass

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

    def _find(
        self, needle: str, forward: bool, use_regex: bool, case_sensitive: bool, *, force: bool = False
    ) -> re.Match[str] | None:
        if not needle:
            return

        haystack = self._editor.content

        pattern = make_needle(needle, use_regex=use_regex, case_sensitive=case_sensitive)
        ctx = self._editor._cursor.context()

        if not (result := find_text(pattern, haystack, forward, ctx, force=force)):
            self._status_bar.ephemeral("No matches found")
            return

        self._editor._cursor.select(*result.match.span())
        self._find_toolbar.set_label(result.index, result.num_matches)

        if result.wraparound:
            template = "Reached {} of page, continuing from the {}"
            args = ("bottom", "top") if forward else ("top", "bottom")
            self._status_bar.ephemeral(template.format(*args))

        return result.match

    def _replace(self, needle: str, replacement: str, replace_all: bool, use_regex: bool, case_sensitive: bool) -> None:
        if replace_all:
            # the easy case - just do a straight text replacement across the document
            pattern = make_needle(needle, use_regex=use_regex, case_sensitive=case_sensitive)
            self._editor.content = re.sub(pattern, replacement, self._editor.content)
            return

        if not (
            match := self._find(needle, forward=True, use_regex=use_regex, case_sensitive=case_sensitive, force=True)
        ):
            return

        start, end = match.span()
        repl = match.expand(replacement)
        self._editor.content = self._editor.content[:start] + repl + self._editor.content[end:]
        self._editor._cursor.select(start, start + len(repl))

    def _on_change(self) -> None:
        """Called when the editor pane's content changes. Registers the update for the preview pane."""
        self.dirty = True
        self._editor.remove_syntax_errors()
        self._render_timer.start()  # debounce
        self._autosave_timer.start()

    def _compile(self) -> None:
        """Update the content of the preview pane."""
        try:
            script = parser.parse_text(self._editor.content)
        except tomllib.TOMLDecodeError as err:
            # we have to add one to the line number to account for the +++ fence
            self._status_bar.set(f"[L{err.lineno + 1}C{err.lineno}] {err.msg}")
            self._editor.show_syntax_error(err.msg, err.lineno + 1, col=None)
            return

        self._preview.write(script)
        self._scroll_sync(force=True)

        self._status_bar["word-counts"].content = f"[Word Counts] {script.word_count_display}"

    def _insert_header(self) -> None:
        header_template = textwrap.dedent("""\
        +++
        title = "script title"
        author = "script author"
        summary = "script description"
        audience = ["A4A"]  # can include multiple tags, such as ["F4A", "M4A"]
        tags = ["tag1", "tag2"]

        [characters.Alice]  # defines a character named Alice
        aliases = ["A"]     # allows "A: some text" to register as Alice's dialogue
        colour = "#ff6ae6"
        summary: ...

        [characters.Bob]
        aliases = ["B"]
        colour = "#139ad9"
        summary: ...
        +++
        """)
        self._editor.content = f"{header_template}\n{self._editor.content}"

    def _show_help(self) -> None:
        message = textwrap.dedent("""
            T: This is a line of dialogue spoken by the T character.

            This is also spoken by T.

            R: This is spoken by R.

            --Lead a line with two hyphens to assign it to the listener.

            (inline direction) Also by R, with *emphasis*.

            ++Lead a line with two plus signs to mark it as a stage direction.

            // Use two slashes to mark a comment. This shows in the preview, but won't be exported by default.
        """)
        QMessageBox.information(None, "Help", message)

    def _show_about(self) -> None:
        QMessageBox.information(None, "About scriptwrite", "scriptwrite v0.1.0\nⓒ 2026 lilellia")

    def _change_font_size(self, direction: Literal[-1, 0, 1] = 0) -> None:
        if direction == 0:
            self._font_sizes["current"] = self._font_sizes["default"]
        else:
            self._font_sizes["current"] += direction

        f = self._font_sizes["current"]

        set_font_size(self._editor, f)
        set_font_size(self._preview, f)
        self._preview.update_block_formatting()

    def run(self) -> None:
        super().showMaximized()
        sys.exit(_app.exec())
