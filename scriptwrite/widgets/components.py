from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from html.parser import HTMLParser
from io import StringIO
from os import PathLike
from pathlib import Path
import re
import sys
from typing import Any, cast, Generic, Literal, NamedTuple, Self, TypeAlias, TypeVar

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtCore import QEvent, QFileSystemWatcher, QObject, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QKeySequence,
    QShortcut,
    QTextBlock,
    QTextCursor,
    QTextDocument,
    QTextFragment,
)
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLayout,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMenuBar,
    QSizePolicy,
    QStatusBar,
    QTextEdit,
    QToolButton,
    QWidget,
)
from typing_extensions import overload

from scriptwrite.widgets.signals import QtSignalProperty
from scriptwrite.widgets.utils import (
    anchors_of,
    build_qindex_map,
    convert_string_index_to_utf16,
    convert_utf16_index_to_python,
)

C = TypeVar("C")
Q = TypeVar("Q", bound=QWidget)
T = TypeVar("T")

F: TypeAlias = Callable[[], None]


class QtProperty(Generic[T]):
    def __init__(self, getter: str, setter: str | None = None) -> None:
        self._get_name = getter
        self._set_name = f"set{getter[0].upper()}{getter[1:]}" if setter is None else setter

    @overload
    def __get__(self, instance: None, owner: type[Q], /) -> Self: ...

    @overload
    def __get__(self, instance: Q, owner: type[Q], /) -> T: ...

    def __get__(self, instance: Q | None, owner: type[Q], /) -> Self | T:
        if instance is None:
            return self

        get = getattr(instance, self._get_name)
        return get()

    def __set__(self, instance: QWidget | None, value: T, /) -> None:
        if instance is None:
            return

        set = getattr(instance, self._set_name)
        set(value)


class Action(QAction):
    callback: QtSignalProperty = QtSignalProperty(signal_name="triggered")
    on_toggle: QtSignalProperty = QtSignalProperty(signal_name="toggled")
    checked: QtProperty[bool] = QtProperty(getter="isChecked", setter="setChecked")

    def __init__(
        self,
        text: str,
        parent: QWidget | None = None,
        *,
        callback: F | None = None,
        tooltip: str | None = None,
        shortcut: str | None = None,
        checkable: bool = False,
        width: int | None = None,
    ) -> None:
        kwargs = {}

        if tooltip:
            kwargs["toolTip"] = tooltip

        if shortcut:
            kwargs["shortcut"] = QKeySequence(shortcut)

        super().__init__(text, parent, checkable=checkable, **kwargs)
        self.callback = callback

    @property
    def keys(self) -> str:
        return super().shortcut().toString()

    @keys.setter
    def keys(self, value: str, /) -> None:
        super().setShortcut(QKeySequence(value))

    def bind(
        self,
        target: QWidget | None = None,
    ) -> Self:
        if target is None:
            if (p := super().parent()) is None:
                raise ValueError("Action is not bindable without specified target.")

            target = cast(QWidget, p)

        target.addAction(self)
        return self


class Shortcut(QShortcut):
    callback: QtSignalProperty = QtSignalProperty("activated")

    def __init__(
        self,
        key: str,
        parent: QWidget,
        *,
        callback: F | None = None,
        scope: Literal["application", "window", "widget", "contained"] = "window",
    ) -> None:
        super().__init__(QKeySequence(key), parent)
        self.scope = scope
        self.callback = callback

    @property
    def scope(self) -> Literal["application", "window", "widget", "contained"]:
        match super().context():
            case Qt.ShortcutContext.ApplicationShortcut:
                return "application"
            case Qt.ShortcutContext.WindowShortcut:
                return "window"
            case Qt.ShortcutContext.WidgetShortcut:
                return "widget"
            case Qt.ShortcutContext.WidgetWithChildrenShortcut:
                return "contained"

    @scope.setter
    def scope(self, value: Literal["application", "window", "widget", "contained"], /) -> None:
        context = {
            "application": Qt.ShortcutContext.ApplicationShortcut,
            "window": Qt.ShortcutContext.WindowShortcut,
            "widget": Qt.ShortcutContext.WidgetShortcut,
            "contained": Qt.ShortcutContext.WidgetWithChildrenShortcut,
        }[value]

        super().setContext(context)


@dataclass(frozen=True, slots=True)
class MenuItemData:
    name: str
    callback: F | None
    shortcut: str | None = field(default=None, kw_only=True)


class MenuBar(QMenuBar):
    def __init__(
        self, parent: QMainWindow, *args: Any, menus: dict[str, Iterable[MenuItemData]] | None = None, **kwargs: Any
    ) -> None:
        super().__init__(parent, *args, **kwargs)
        self._menus: dict[str, QMenu] = {}

        if menus:
            self._add_menus(menus)

        parent.setMenuBar(self)

    def _add_menu(self, name: str, items: Iterable[MenuItemData]):
        menu = cast(QMenu, super().addMenu(name))

        for item in items:
            if item.name == "---":
                menu.addSeparator()
                continue

            action = Action(item.name, menu, callback=item.callback, shortcut=item.shortcut)
            menu.addAction(action)

        self._menus[name] = menu

    def _add_menus(self, menus: dict[str, Iterable[MenuItemData]]) -> None:
        for name, items in menus.items():
            self._add_menu(name, items)


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


def debouncable_timer(msecs: int, callback: Callable[[], None]) -> QTimer:
    """Create a timer with the given delay that executes the given callback when time elapses."""
    timer = QTimer(singleShot=True, interval=msecs)
    timer.timeout.connect(callback)

    return timer


class ToolButton(QToolButton):
    def __init__(self, action: Action, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        super().setDefaultAction(action)
        super().setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        super().setAutoRaise(True)
        super().setCheckable(action.isCheckable())


class Toolbar(QFrame):
    def __init__(self, parent: QMainWindow, *args: Any, **kwargs: Any) -> None:
        super().__init__(parent, *args, **kwargs)

        super().setWindowFlags(Qt.WindowType.Widget | Qt.WindowType.FramelessWindowHint)

        super().setAutoFillBackground(True)

        super().setFrameShape(QFrame.Shape.Box)
        super().setFrameShadow(QFrame.Shadow.Raised)

    @property
    def master(self) -> QMainWindow | None:
        return cast(QMainWindow | None, super().parentWidget())

    @property
    def is_visible(self) -> bool:
        return super().isVisible()

    @is_visible.setter
    def is_visible(self, value: bool, /) -> None:
        if value:
            super().show()
            self.reposition()
            super().raise_()  # force render with higher z-index
        else:
            super().hide()

    def add_action(
        self,
        text: str,
        *,
        checkable: bool = False,
        callback: F | None = None,
        tooltip: str | None = None,
    ) -> ToolButton:
        action = Action(text, self, callback=callback, tooltip=tooltip, checkable=checkable)
        return ToolButton(action)

    def force_minimal_size(self) -> None:
        if layout := super().layout():
            layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        super().setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def toggle(self) -> None:
        self.is_visible = not self.is_visible

    def reposition(self, margin: int = 5) -> None:
        if self.master is None:
            return

        if (central := self.master.centralWidget()) is None:
            return

        super().adjustSize()

        g = central.geometry()

        if g.width() <= 0 or g.height() <= 0:
            return

        x = g.x() + margin
        y = g.y() + g.height() - super().height() - margin
        super().move(x, y)

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            if self.is_visible:
                self.reposition()

        return super().eventFilter(watched, event)

    def bind(self) -> Self:
        if self.master:
            self.master.installEventFilter(self)  # track parent resizing

        super().hide()
        return self


class ToolbarActionGroup:
    def __init__(self, *buttons: ToolButton) -> None:
        self.buttons: list[ToolButton] = list(buttons)

    def add(self, button: ToolButton) -> ToolButton:
        self.buttons.append(button)
        return button

    def sync_widths(self) -> None:
        """Finds the maximum width of the group's widgets and resizes all of them to that size."""
        if not self.buttons:
            return

        max_width = max(b.sizeHint().width() for b in self.buttons)

        for button in self.buttons:
            button.setFixedWidth(max_width)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            return

        self.sync_widths()


class Entry(QLineEdit):
    width_: QtProperty[int] = QtProperty("width", "setFixedWidth")
    on_change: QtSignalProperty = QtSignalProperty(signal_name="textChanged")


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


class TextArea(QTextEdit):
    on_change: QtSignalProperty = QtSignalProperty(signal_name="textChanged")
    on_cursor_move: QtSignalProperty = QtSignalProperty(signal_name="cursorPositionChanged")

    def __init__(self, *args: Any, on_change: F | None = None, on_cursor_move: F | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.on_change = on_change
        self.on_cursor_move = on_cursor_move
        self._cursor = Cursor(parent=self)

    @property
    def doc(self) -> QTextDocument:
        return super().document()

    @property
    def content(self) -> str:
        return super().toPlainText()

    @content.setter
    def content(self, s: str, /) -> None:
        super().setPlainText(s)

    @property
    def html(self) -> str:
        return super().toHtml()

    def _set_html(self, s: str) -> None:
        # bring QTextEdit kicking and screaming into the... slightly less distant past
        s = _HTMLInjector.inject_into(s)
        super().setHtml(s)

    @html.setter
    def html(self, s: str, /) -> None:
        self._set_html(s)

    def scroll_to_block(self, block: QTextBlock, *, align_top: bool = False) -> None:
        self._cursor.scroll_to_block(block)

        if align_top:
            y = self.doc.documentLayout().blockBoundingRect(block).top()
            super().verticalScrollBar().setValue(int(y))

    @contextmanager
    def suppress_signals(self) -> Iterator[None]:
        try:
            super().blockSignals(True)
            yield
        finally:
            super().blockSignals(False)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        super().textCursor().beginEditBlock()
        try:
            yield
        finally:
            super().textCursor().endEditBlock()

    @property
    def font_size(self) -> int | None:
        """Return the editor's font size, in pt. If the system is using pixel sizing, return None."""
        if (size := super().font().pointSize()) <= 0:
            return None

        return size

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

    def blocks(self) -> Iterator[QTextBlock]:
        """Return an iterator over the QTextBlock objects that define the document."""
        curr = self.doc.begin()
        while curr.isValid():
            yield curr
            curr = curr.next()

    @staticmethod
    def fragments_of(block: QTextBlock) -> Iterator[QTextFragment]:
        it = block.begin()
        while not it.atEnd():
            yield it.fragment()
            it += 1

    def fragments(self) -> Iterator[QTextFragment]:
        """Return an iterator over the QTextFragment objects that define the document."""
        for block in self.blocks():
            yield from type(self).fragments_of(block)

    def anchor_names(self) -> Iterator[str]:
        """Return an iterator over all names that define anchors within the document.
        An "anchor" is anything which can be scrolled to via scrollToAnchor.
        """
        for fragment in self.fragments():
            yield from anchors_of(fragment)


class CursorPosition(NamedTuple):
    line: int
    column: int


class Cursor:
    def __init__(self, parent: TextArea):
        self._parent = parent

    @property
    def current(self) -> QTextCursor:
        return cast(QTextCursor, self._parent.textCursor())

    @property
    def position(self) -> CursorPosition:
        current = self.current

        line = current.blockNumber() + 1
        column = current.columnNumber() + 1
        return CursorPosition(line, column)

    @position.setter
    def position(self, value: Iterable[int], /) -> None:
        line, column = value
        block = self._parent.doc.findBlockByLineNumber(line - 1)

        if not block.isValid():
            return

        # clamp column to line length
        col = max(0, min(column - 1, len(block.text())))

        self.scroll_to_index(block.position() + col)

    @property
    def qindex(self) -> int:
        """The current index (characters from the start) of the cursor, in QChar (utf-16)."""
        return self.current.position()

    @qindex.setter
    def qindex(self, value: int, /) -> None:
        self.current.setPosition(value)

    def get_index(self) -> int:
        """The current index (characters from the start) of the cursor."""
        return convert_utf16_index_to_python(self._parent.content, self.qindex)

    def move_to(self, index: int, *, select_between: bool = False) -> None:
        q = convert_string_index_to_utf16(self._parent.content, index)
        self._move_to_qindex(q, select_between=select_between)

    def _move_to_qindex(self, qindex: int, *, select_between: bool = False) -> None:
        mode = QTextCursor.MoveMode.KeepAnchor if select_between else QTextCursor.MoveMode.MoveAnchor
        self.current.setPosition(qindex, mode=mode)

    def scroll_to_index(self, index: int) -> None:
        self.move_to(index)
        self.update()

    def scroll_to_block(self, block: QTextBlock) -> None:
        self._move_to_qindex(block.position())
        self.update()

    def select(self, start: int, end: int) -> None:
        """Force selection of the range [start, end)."""
        qindex_map = build_qindex_map(self._parent.content[:end])
        self._move_to_qindex(qindex_map[start])
        self._move_to_qindex(qindex_map[end], select_between=True)
        self.update()

    @property
    def selected_text(self) -> str:
        if self.current.hasSelection():
            return self.current.selectedText()

        return ""

    def update(self) -> None:
        self._parent.setTextCursor(self.current)
        self._parent.ensureCursorVisible()


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
