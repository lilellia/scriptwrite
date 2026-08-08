from typing import Literal, overload, Self, TypeVar

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLayout, QVBoxLayout, QWidget

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


class FlexGrid(QGridLayout):
    def __init__(self, parent: QWidget | None, *items: QWidget, max_columns: int) -> None:
        super().__init__(parent)
        self._items: list[QWidget] = []
        self._max_columns = max_columns

        self._row, self._col = 0, 0

        for item in items:
            self.add(item)

    @property
    def max_columns(self) -> int:
        return self._max_columns

    @max_columns.setter
    def max_columns(self, value: int, /) -> None:
        self._max_columns = value
        self.reflow()

    def _place(self, item: Q) -> Q:
        super().addWidget(item, self._row, self._col)

        # update cursor
        self._col += 1
        if self._col >= self.max_columns:
            self._row += 1
            self._col = 0

        return item

    def add(self, item: Q) -> Q:
        self._place(item)
        self._items.append(item)
        return item

    def reflow(self) -> None:
        self._row, self._col = 0, 0

        for item in self._items:
            super().removeWidget(item)
            self._place(item)

    def remove(self, item: QWidget) -> None:
        super().removeWidget(item)
        self._items.remove(item)
        self.reflow()
