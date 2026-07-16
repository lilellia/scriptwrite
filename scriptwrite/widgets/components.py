from __future__ import annotations

import sys
from typing import Any, cast, Self

from scriptwrite.widgets.actions import Action, ToolButton
from scriptwrite.widgets.frame import Frame

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import (
    QLayout,
    QMainWindow,
    QSizePolicy,
)

from scriptwrite.types import F


def debouncable_timer(msecs: int, callback: F) -> QTimer:
    """Create a timer with the given delay that executes the given callback when time elapses."""
    timer = QTimer(singleShot=True, interval=msecs)
    timer.timeout.connect(callback)

    return timer


class Toolbar(Frame):
    def __init__(self, parent: QMainWindow, *args: Any, **kwargs: Any) -> None:
        super().__init__(parent, *args, **kwargs)

        super().setWindowFlags(Qt.WindowType.Widget | Qt.WindowType.FramelessWindowHint)

        self.autofill_bg = True
        self.frame_shape = "box"
        self.frame_shadow = "raised"

    @property
    def master(self) -> QMainWindow | None:
        return cast(QMainWindow | None, super().parentWidget())

    @property
    def is_visible(self) -> bool:
        return super().isVisible()

    @is_visible.setter
    def is_visible(self, value: bool, /) -> None:
        if value:
            super().show()
            self.reposition()
            super().raise_()  # force render with higher z-index
        else:
            super().hide()

    def add_action(
        self,
        text: str,
        *,
        checkable: bool = False,
        callback: F | None = None,
        tooltip: str | None = None,
    ) -> ToolButton:
        action = Action(text, self, callback=callback, tooltip=tooltip, checkable=checkable)
        return ToolButton(action)

    def force_minimal_size(self) -> None:
        if layout := super().layout():
            layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        super().setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def toggle(self) -> None:
        self.is_visible = not self.is_visible

    def reposition(self, margin: int = 5) -> None:
        if self.master is None:
            return

        if (central := self.master.centralWidget()) is None:
            return

        super().adjustSize()

        g = central.geometry()

        if g.width() <= 0 or g.height() <= 0:
            return

        x = g.x() + margin
        y = g.y() + g.height() - super().height() - margin
        super().move(x, y)

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            if self.is_visible:
                self.reposition()

        return super().eventFilter(watched, event)

    def bind(self) -> Self:
        if self.master:
            self.master.installEventFilter(self)  # track parent resizing

        super().hide()
        return self


class ToolbarActionGroup:
    def __init__(self, *buttons: ToolButton) -> None:
        self.buttons: list[ToolButton] = list(buttons)

    def add(self, button: ToolButton) -> ToolButton:
        self.buttons.append(button)
        return button

    def sync_widths(self) -> None:
        """Finds the maximum width of the group's widgets and resizes all of them to that size."""
        if not self.buttons:
            return

        max_width = max(b.sizeHint().width() for b in self.buttons)

        for button in self.buttons:
            button.setFixedWidth(max_width)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            return

        self.sync_widths()
