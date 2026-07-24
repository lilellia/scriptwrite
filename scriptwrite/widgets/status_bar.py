from typing import Any

from PySide6.QtWidgets import QStatusBar, QWidget

from scriptwrite.widgets.text import Label
from scriptwrite.widgets.timer import Timer


class StatusBar(QStatusBar):
    def __init__(self, parent: QWidget | None = None, *args: Any, **kwargs: Any) -> None:
        super().__init__(parent, *args, **kwargs)
        self.widgets: dict[str, Label] = {}
        self._permanent_message: str = ""
        self._restore_permanent_timer: Timer | None = None

    def add_label(self, name: str, initial_text: str | None = None) -> Label:
        widget = Label(initial_text)
        super().addPermanentWidget(widget)
        self.widgets[name] = widget
        return widget

    def __getitem__(self, key: str) -> Label:
        return self.widgets[key]

    def _restore_permanent_message(self) -> None:
        super().showMessage(self._permanent_message)

    def set(self, message: str = "") -> None:
        self._permanent_message = message
        super().showMessage(message)

    def ephemeral(self, message: str, duration: int = 2500) -> None:
        super().showMessage(message, duration)

        self._restore_permanent_timer = Timer(duration, self._restore_permanent_message)
        self._restore_permanent_timer.start()
