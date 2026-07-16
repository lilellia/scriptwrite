from __future__ import annotations

from PySide6.QtCore import QTimer

from scriptwrite.types import F
from scriptwrite.widgets.descriptors import QtProperty
from scriptwrite.widgets.signals import QtSignalProperty


class Timer(QTimer):
    single_shot: QtProperty[bool] = QtProperty("singleShot")
    duration: QtProperty[int] = QtProperty("interval")
    callback: QtSignalProperty = QtSignalProperty("timeout")

    def __init__(self, duration: int, callback: F | None = None) -> None:
        super().__init__()
        self.single_shot = True
        self.duration = duration
        self.callback = callback
