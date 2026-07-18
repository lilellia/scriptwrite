from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast, NamedTuple, TYPE_CHECKING

from PySide6.QtGui import QTextBlock, QTextCursor

if TYPE_CHECKING:
    # TextArea holds a reference to Cursor, so we end up in an import cycle without the TYPE_CHECKING guard
    from scriptwrite.widgets.text import TextArea


def convert_string_index_to_utf16(text: str, idx: int) -> int:
    """Convert a Python character index to a Qt UTF-16 position."""
    return sum(2 if ord(char) else 1 for char in text[:idx])


def convert_utf16_index_to_python(text: str, idx: int) -> int:
    """Convert a Qt UTF-16 position to a Python character index."""
    qindex = 0
    for py_index, char in enumerate(text):
        if qindex >= idx:
            return py_index

        qindex += 2 if ord(char) > 0xFFFF else 1

    return len(text)


def build_qindex_map(text: str) -> dict[int, int]:
    """Return a map of {index: qindex} for the given string."""
    mapping: dict[int, int] = {0: 0}

    index = qindex = 0
    for index, char in enumerate(text):
        mapping[index] = qindex
        qindex += 2 if ord(char) > 0xFFFF else 1

    mapping[index] = qindex

    return mapping


class CursorPosition(NamedTuple):
    line: int
    column: int


@dataclass(slots=True, frozen=True)
class CursorContext:
    index: int
    selected_range: tuple[int, int] | None
    selected_text: str


class Cursor:
    def __init__(self, parent: TextArea):
        self._parent = parent

    def _get(self) -> QTextCursor:
        return cast(QTextCursor, self._parent.textCursor())

    @property
    def position(self) -> CursorPosition:
        _cur = self._get()

        line = _cur.blockNumber() + 1
        column = _cur.columnNumber() + 1
        return CursorPosition(line, column)

    @position.setter
    def position(self, value: Iterable[int], /) -> None:
        line, column = value
        block = self._parent.doc.findBlockByLineNumber(line - 1)

        if not block.isValid():
            return

        # clamp column to line length
        col = max(0, min(column - 1, len(block.text())))

        self._move_to_qindex(block.position() + col)

    @property
    def qindex(self) -> int:
        """The current index (characters from the start) of the cursor, in QChar (utf-16)."""
        return self._get().position()

    @qindex.setter
    def qindex(self, value: int, /) -> None:
        _cur = self._get()
        _cur.setPosition(value)
        self.update(_cur)

    def get_index(self) -> int:
        """The current index (characters from the start) of the cursor."""
        return convert_utf16_index_to_python(self._parent.content, self.qindex)

    def current_block(self) -> QTextBlock:
        return self._get().block()

    def move_to(self, index: int, *, select_between: bool = False) -> None:
        q = convert_string_index_to_utf16(self._parent.content, index)
        self._move_to_qindex(q, select_between=select_between)

    def _move_to_qindex(self, qindex: int, *, select_between: bool = False) -> None:
        mode = QTextCursor.MoveMode.KeepAnchor if select_between else QTextCursor.MoveMode.MoveAnchor

        _cur = self._get()
        _cur.setPosition(qindex, mode=mode)
        self.update(_cur)

    def move_to_block(self, block: QTextBlock) -> None:
        self._move_to_qindex(block.position())

    def select(self, start: int, end: int) -> None:
        """Force selection of the range [start, end)."""
        qindex_map = build_qindex_map(self._parent.content[:end])
        self._move_to_qindex(qindex_map[end - 1])
        self._move_to_qindex(qindex_map[start], select_between=True)
        self._parent.align_screen_view_to_block(self.current_block())

    @property
    def selected_range(self) -> tuple[int, int] | None:
        if _cur := self._get():
            q1, q2 = _cur.selectionStart(), _cur.selectionEnd()

            # because qindices are always larger than their index counterparts, [:q2] is guaranteed to be sufficient
            qindex_map = build_qindex_map(self._parent.content[:q2])
            i1 = next(i for i, q in qindex_map.items() if q >= q1)
            i2 = next(i for i, q in qindex_map.items() if q >= q2) + 1  # to account for exclusive RHS

            return i1, i2

    @property
    def selected_text(self) -> str:
        if (_cur := self._get()).hasSelection():
            return _cur.selectedText()

        return ""

    def update(self, cur: QTextCursor) -> None:
        self._parent.setTextCursor(cur)
        self._parent.ensureCursorVisible()

    def context(self) -> CursorContext:
        return CursorContext(
            index=self.get_index(), selected_range=self.selected_range, selected_text=self.selected_text
        )
