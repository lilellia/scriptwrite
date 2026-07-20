from collections.abc import Iterator
from contextlib import contextmanager
from html.parser import HTMLParser
from io import StringIO
import re
import sys
from typing import Any, cast

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPaintEvent, QTextBlock, QTextDocument, QTextFormat, QTextFragment
from PySide6.QtWidgets import QLabel, QLineEdit, QTextEdit, QWidget

from scriptwrite.widgets.actions import AnimatedAction
from scriptwrite.widgets.cursor import Cursor
from scriptwrite.widgets.display import Color, fill_rect

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from scriptwrite.types import F
from scriptwrite.widgets.descriptors import QtProperty
from scriptwrite.widgets.signals import QtSignalProperty


def anchors_of(fragment: QTextFragment) -> Iterator[str]:
    """Return an iterator over the anchors within the given text fragment."""
    if (fmt := fragment.charFormat()).isAnchor():
        if names := fmt.property(QTextFormat.Property.AnchorName):
            yield from names


class Entry(QLineEdit):
    width_: QtProperty[int] = QtProperty("width", "setFixedWidth")
    content: QtProperty[str] = QtProperty("text")
    placeholder: QtProperty[str] = QtProperty("placeholderText")
    on_change: QtSignalProperty = QtSignalProperty("textChanged")

    def __init__(
        self,
        parent: QWidget | None = None,
        text: str = "",
        *args: Any,
        placeholder: str = "",
        width: int | None = None,
        on_change: F | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.content = text
        self.placeholder = placeholder

        if width is not None:
            self.width_ = width

        self.on_change = on_change


class Label(QLabel):
    @property
    def content(self) -> str:
        return super().text()

    @content.setter
    def content(self, s: str, /) -> None:
        super().setText(s)


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
    content: QtProperty[str] = QtProperty(getter="toPlainText", setter="setPlainText")

    def __init__(self, *args: Any, on_change: F | None = None, on_cursor_move: F | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.on_change = on_change
        self.on_cursor_move = on_cursor_move
        self._cursor = Cursor(parent=self)

        # improve selection highlight colour contrast
        self._selection_color = Color.from_hex("#3E5D74")
        super().setStyleSheet(f""" QTextEdit {{ selection-background-color: {self._selection_color.as_hex()}; }} """)

        # implement block highlighting
        self._highlight_color = Color.from_hex("#FFF3CD")
        self._highlighted_block: QTextBlock | None = None
        self._highlight_animation: AnimatedAction[int] | None = None

    @property
    def doc(self) -> QTextDocument:
        return super().document()

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

    def _block_bbox(self, block: QTextBlock) -> QRectF:
        return self.doc.documentLayout().blockBoundingRect(block)

    def align_screen_view_to_block(self, block: QTextBlock) -> None:
        viewport_height = super().viewport().height()
        block_rect = self._block_bbox(block)

        y = block_rect.top() - (viewport_height * 0.5) + (block_rect.height() * 0.5)
        super().verticalScrollBar().setValue(int(y))

    def scroll_to_block(self, block: QTextBlock, *, align: bool = False) -> None:
        self._cursor.move_to_block(block)

        if align:
            self.align_screen_view_to_block(block)

    def highlight_current_block(self, *, duration: int = 2500) -> None:
        self._highlighted_block = self._cursor.current_block()

        def _remove_highlight() -> None:
            self._highlighted_block = None

        self._highlight_animation = AnimatedAction(
            initial_value=0x30,
            final_value=0,
            length=duration,
            ease="in-expo",
            on_update=self.viewport().update,
            on_finish=_remove_highlight,
        )
        self._highlight_animation.start()

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        if self._highlighted_block:
            assert self._highlight_animation is not None
            color = self._highlight_color.with_alpha(self._highlight_animation.value)

            bbox = self._block_bbox(self._highlighted_block)
            y = bbox.top() - self.verticalScrollBar().value()
            fill_rect(self.viewport(), x=0, y=y, width=self.viewport().width(), height=bbox.height(), color=color)

        super().paintEvent(event)

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

    def get_block_at_line(self, line: int) -> QTextBlock | None:
        if 1 <= line <= self.doc.blockCount():
            return self.doc.findBlockByLineNumber(line - 1)

        return None

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
