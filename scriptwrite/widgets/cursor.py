from collections.abc import Iterable
from typing import cast, NamedTuple, TYPE_CHECKING

from PySide6.QtGui import QTextBlock, QTextCursor

if TYPE_CHECKING:
    # TextArea holds a reference to Cursor, so we end up in an import cycle without the TYPE_CHECKING guard
    from scriptwrite.widgets.text import TextArea


def convert_string_index_to_utf16(text: str, idx: int) -> int:
    """Convert a Python character index to a Qt UTF-16 position."""
    return len(text[:idx].encode("utf-16-le")) // 2


def convert_utf16_index_to_python(text: str, idx: int) -> int:
    """Convert a Qt UTF-16 position to a Python character index."""
    qindex = 0
    for py_index, char in enumerate(text):
        if qindex >= idx:
            return py_index

        qindex += len(char.encode("utf-16-le")) // 2

    return len(text)


def build_qindex_map(text: str) -> dict[int, int]:
    """Return a map of {index: qindex} for the given string."""
    mapping: dict[int, int] = {0: 0}

    qindex = 0
    for index, char in enumerate(text):
        qindex += len(char.encode("utf-16-le")) // 2
        mapping[index] = qindex

    return mapping


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
