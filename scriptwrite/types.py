from collections.abc import Callable
from typing import TypeAlias, TypeVar

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

F: TypeAlias = Callable[[], None]
Q = TypeVar("Q", bound=QObject)
W = TypeVar("W", bound=QWidget)
