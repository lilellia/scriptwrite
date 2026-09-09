from __future__ import annotations

from dataclasses import asdict
from typing import Any

from PySide6.QtWidgets import QStatusBar, QWidget

from scriptwrite.log import Handler, Level, logger, Record
from scriptwrite.widgets.text import Label
from scriptwrite.widgets.timer import Timer


class StatusBar(QStatusBar):
    def __init__(self, parent: QWidget | None = None, *args: Any, **kwargs: Any) -> None:
        super().__init__(parent, *args, **kwargs)
        self.widgets: dict[str, Label] = {}
        self._permanent_message: str = ""
        self._restore_permanent_timer: Timer | None = None

    def hook_logger(self, level: Level = Level.WARNING) -> StatusBarHandler:
        handler = StatusBarHandler(self, level=level)
        return logger.add_handler(handler)

    def add_label(self, name: str, initial_text: str | None = None) -> Label:
        widget = Label(initial_text)
        super().addPermanentWidget(widget)
        self.widgets[name] = widget
        return widget

    def __getitem__(self, key: str) -> Label:
        return self.widgets[key]

    def _restore_permanent_message(self) -> None:
        super().showMessage(self._permanent_message)

    def set(self, message: str = "", *, force: bool = True) -> None:
        self._permanent_message = message
        if force:
            super().showMessage(message)

    def ephemeral(self, message: str, duration: int = 2500) -> None:
        super().showMessage(message, duration)

        self._restore_permanent_timer = Timer(duration, self._restore_permanent_message)
        self._restore_permanent_timer.start()


class StatusBarHandler(Handler):
    def __init__(self, parent: StatusBar, level: Level = Level.WARNING):
        super().__init__(level=level, filter=None)
        self.parent = parent

    def emit(self, record: Record, **extra: Any) -> None:
        if not self.should_emit(record):
            return

        kw = asdict(record)
        if extra:
            kw["message"] = f"{record.message} (kwargs={extra})"

        output = f"{record.level.name}: {kw['message']}"
        self.parent.ephemeral(output, duration=3500)
