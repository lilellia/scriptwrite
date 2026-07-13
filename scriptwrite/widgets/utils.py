from collections.abc import Iterator

from PySide6.QtGui import QTextFormat, QTextFragment


def anchors_of(fragment: QTextFragment) -> Iterator[str]:
    """Return an iterator over the anchors within the given text fragment."""
    if (fmt := fragment.charFormat()).isAnchor():
        if names := fmt.property(QTextFormat.Property.AnchorName):
            yield from names


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
