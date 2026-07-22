from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import sys
from typing import Any, cast, Literal, Self

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QPaintEvent,
    QTextBlock,
    QTextBlockFormat,
    QTextBlockUserData,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextFragment,
)
from PySide6.QtWidgets import QLabel, QLineEdit, QTextEdit, QWidget

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from scriptwrite.log import logger
from scriptwrite.types import F
from scriptwrite.widgets.actions import AnimatedAction
from scriptwrite.widgets.cursor import Cursor
from scriptwrite.widgets.descriptors import QtProperty
from scriptwrite.widgets.display import Color, fill_rect, TextStyle
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
            self._highlight_animation = None

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
        if self._highlighted_block and self._highlight_animation:
            if self._highlighted_block.isValid():
                color = self._highlight_color.with_alpha(self._highlight_animation.value)

                bbox = self._block_bbox(self._highlighted_block)
                y = bbox.top() - self.verticalScrollBar().value()
                fill_rect(self.viewport(), x=0, y=y, width=self.viewport().width(), height=bbox.height(), color=color)
            else:
                # the block doesn't exist anymore, so force-stop the animation
                if f := self._highlight_animation.on_finish:
                    f()

                self._highlight_animation = None

        super().paintEvent(event)

    @contextmanager
    def suppress_signals(self) -> Iterator[None]:
        try:
            super().blockSignals(True)
            yield
        finally:
            super().blockSignals(False)

    @contextmanager
    @staticmethod
    def suppress_edits(document: QTextDocument) -> Iterator[None]:
        old = document.isUndoRedoEnabled()
        try:
            document.setUndoRedoEnabled(False)
            yield
        finally:
            document.setUndoRedoEnabled(old)

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


class BlockFormat:
    def __init__(
        self,
        block: QTextBlock,
        *,
        alignment: Literal["left", "right", "center", "justify"] | None = None,
        heading: Literal[0, 1, 2, 3, 4, 5, 6] | None = None,
        indent_level: int | None = None,
        margin_left: float | None = None,
        margin_right: float | None = None,
        margin_bottom: float | None = None,
        margin_top: float | None = None,
        font_size: float | None = None,
    ) -> None:
        super().__init__()

        self.cursor = QTextCursor(block)

        if alignment is not None:
            self.align = alignment

        if heading is not None:
            self.heading = heading

        if indent_level is not None:
            self.indent_level = indent_level

        if margin_left is not None:
            self.margin_left = margin_left

        if margin_right is not None:
            self.margin_right = margin_right

        if margin_bottom is not None:
            self.margin_bottom = margin_bottom

        if margin_top is not None:
            self.margin_top = margin_top

        if font_size is not None:
            self.font_size = font_size

    def _pull(self) -> QTextBlockFormat:
        if not self.cursor.block().isValid():
            logger.warning("Tried to access format for invalid block")

        return self.cursor.blockFormat()

    def _set(self, key: str, value: Any) -> None:
        with TextArea.suppress_edits(self.cursor.block().document()):
            f = self._pull()
            getattr(f, f"set{key}")(value)
            self._push(f)

    def _push(self, f: QTextBlockFormat) -> None:
        self.cursor.setBlockFormat(f)

    def as_format(self) -> QTextBlockFormat:
        f = self._pull()
        return f

    @property
    def align(self) -> Literal["left", "right", "center", "justify"]:
        flag = self._pull().alignment()

        if flag & Qt.AlignmentFlag.AlignLeft:
            return "left"

        if flag & Qt.AlignmentFlag.AlignRight:
            return "right"

        if flag & Qt.AlignmentFlag.AlignHCenter:
            return "center"

        if flag & Qt.AlignmentFlag.AlignJustify:
            return "justify"

        return "left"

    @align.setter
    def align(self, value: Literal["left", "right", "center", "justify"], /) -> None:
        lookup = {
            "left": Qt.AlignmentFlag.AlignLeft,
            "right": Qt.AlignmentFlag.AlignRight,
            "center": Qt.AlignmentFlag.AlignHCenter,
            "justify": Qt.AlignmentFlag.AlignJustify,
        }

        self._set("Alignment", lookup[value])

    @property
    def heading(self) -> Literal[0, 1, 2, 3, 4, 5, 6]:
        return cast(Literal[0, 1, 2, 3, 4, 5, 6], self._pull().headingLevel())

    @heading.setter
    def heading(self, value: Literal[0, 1, 2, 3, 4, 5, 6], /) -> None:
        self._set("HeadingLevel", value)

    @property
    def indent_spaces(self) -> int:
        return self._pull().indent()

    @indent_spaces.setter
    def indent_spaces(self, value: int, /) -> None:
        self._set("Indent", value)

    @property
    def margin_left(self) -> float:
        return self._pull().leftMargin()

    @margin_left.setter
    def margin_left(self, value: float, /) -> None:
        self._set("LeftMargin", value)

    @property
    def margin_right(self) -> float:
        return self._pull().rightMargin()

    @margin_right.setter
    def margin_right(self, value: float, /) -> None:
        self._set("RightMargin", value)

    @property
    def margin_top(self) -> float:
        return self._pull().topMargin()

    @margin_top.setter
    def margin_top(self, value: float, /) -> None:
        self._set("TopMargin", value)

    @property
    def margin_bottom(self) -> float:
        return self._pull().bottomMargin()

    @margin_bottom.setter
    def margin_bottom(self, value: float, /) -> None:
        self._set("BottomMargin", value)

    @property
    def font_size(self) -> float:
        return self.cursor.blockCharFormat().fontPointSize()

    @font_size.setter
    def font_size(self, value: float, /) -> None:
        with TextArea.suppress_edits(self.cursor.block().document()):
            delta = QTextCharFormat()
            delta.setFontPointSize(value)

            fmt = self.cursor.blockCharFormat()
            fmt.setFontPointSize(value)
            self.cursor.setBlockCharFormat(fmt)

            cur = QTextCursor(self.cursor)
            cur.select(QTextCursor.SelectionType.BlockUnderCursor)

            if cur.hasSelection():
                cur.mergeCharFormat(delta)


class UserData(QTextBlockUserData):
    def __init__(self, **kwargs: Any):
        super().__init__()
        self.kwargs = kwargs

    def __str__(self) -> str:
        return str(self.kwargs)


class TextBlock:
    def __init__(self, cursor: QTextCursor, **metadata: Any) -> None:
        self.cursor = cursor
        self.metadata = metadata

    @property
    def format(self) -> BlockFormat:
        return BlockFormat(self.cursor.block())

    @format.setter
    def format(self, value: BlockFormat, /) -> None:
        self.cursor.setBlockFormat(value.as_format())

    def write(self, text: str, format: TextStyle) -> None:
        # apply `format` on top of the existing block style
        style = self.cursor.blockCharFormat()
        style.merge(format)

        self.cursor.insertText(text, style)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        if exc_type is not None:
            return

        block = self.cursor.block()

        if self.metadata:
            block.setUserData(UserData(**self.metadata))

        self.cursor.insertBlock()

        # reset formatting for following blocks
        default = QTextCharFormat()
        self.cursor.setBlockCharFormat(default)
        self.cursor.setCharFormat(default)
