from collections.abc import Iterator

from PySide6.QtGui import QTextFormat, QTextFragment


def anchors_of(fragment: QTextFragment) -> Iterator[str]:
    """Return an iterator over the anchors within the given text fragment."""
    if (fmt := fragment.charFormat()).isAnchor():
        if names := fmt.property(QTextFormat.Property.AnchorName):
            yield from names
