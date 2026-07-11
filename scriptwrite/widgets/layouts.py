from collections.abc import Iterable

from PySide6.QtWidgets import QGridLayout, QWidget


def make_layout(widgets: Iterable[Iterable[QWidget]]) -> QGridLayout:
    canvas = QGridLayout()

    for y, row in enumerate(widgets):
        for x, widget in enumerate(row):
            canvas.addWidget(widget, y, x)

    return canvas
