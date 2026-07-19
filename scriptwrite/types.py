from collections.abc import Callable
from typing import TypeAlias, TypeVar

from PySide6.QtCore import QObject
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import QWidget

QtValueType: TypeAlias = QTextCharFormat | QColor

F: TypeAlias = Callable[[], None]
Q = TypeVar("Q", bound=QObject | QtValueType)
W = TypeVar("W", bound=QWidget)
