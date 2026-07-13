from typing import Literal, overload, Self, TypeVar

from PySide6.QtWidgets import QHBoxLayout, QLayout, QVBoxLayout, QWidget

Q = TypeVar("Q", bound=QWidget)


class Box:
    PROXY_CLASSES = {"horizontal": QHBoxLayout, "vertical": QVBoxLayout}

    def __init__(
        self, parent: QWidget | Self, direction: Literal["horizontal", "vertical"], *, stretch: bool = False
    ) -> None:
        self.direction = direction
        self.parent = parent
        self.stretch = stretch
        self._proxied = type(self).PROXY_CLASSES[direction]()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        if exc_type is not None:
            return

        if isinstance(self.parent, QWidget):
            self.parent.setLayout(self._proxied)
            if not self.stretch:
                self._proxied.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        elif isinstance(self.parent, type(self)):
            self.parent.add(self)

    @overload
    def add(self, obj: Q) -> Q: ...

    @overload
    def add(self, obj: Self) -> Self: ...

    def add(self, obj: Q | Self) -> Q | Self:
        if isinstance(obj, QWidget):
            self._proxied.addWidget(obj)
        elif isinstance(obj, type(self)):
            self._proxied.addLayout(obj._proxied)
        else:
            raise ValueError(f"Cannot add object of type {type(obj).__name__}")

        return obj

    def add_stretch(self) -> None:
        self._proxied.addStretch()
