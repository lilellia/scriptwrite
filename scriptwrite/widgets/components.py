from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, cast

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QLabel, QMenu, QMenuBar, QStatusBar, QWidget


@dataclass(frozen=True, slots=True)
class _MenuItemData:
    name: str
    callback: Callable[[], None] | None
    shortcut: str | None = field(default=None, kw_only=True)


class _MenuBarProxy:
    def __init__(self, menubar: QMenuBar, *, menus: dict[str, Iterable[_MenuItemData]] | None = None) -> None:
        self._proxied = menubar
        self._menus: dict[str, QMenu] = {}

        if menus:
            self._add_menus(menus)

    def _add_menus(self, menus: dict[str, Iterable[_MenuItemData]]) -> None:
        for name, items in menus.items():
            self._add_menu(name, items)

    def _add_menu(self, name: str, items: Iterable[_MenuItemData]) -> None:
        menu = cast(QMenu, self._proxied.addMenu(name))

        for item in items:
            if item.name == "---":
                menu.addSeparator()
                continue

            action = QAction(item.name, menu)

            if item.callback is not None:
                action.triggered.connect(item.callback)

            if item.shortcut:
                action.setShortcut(QKeySequence(item.shortcut))

            menu.addAction(action)

        self._menus[name] = menu

    def __getattr__(self, key: Any) -> Any:
        return getattr(self._proxied, key)


class Label(QLabel):
    @property
    def content(self) -> str:
        return super().text()

    @content.setter
    def content(self, s: str, /) -> None:
        super().setText(s)


class StatusBar(QStatusBar):
    def __init__(self, parent: QWidget | None = None, *args: Any, **kwargs: Any) -> None:
        super().__init__(parent, *args, **kwargs)
        self.widgets: dict[str, Label] = {}

    def add_label(self, name: str, initial_text: str | None = None) -> Label:
        widget = Label(initial_text)
        super().addPermanentWidget(widget)
        self.widgets[name] = widget
        return widget

    def __getitem__(self, key: str) -> Label:
        return self.widgets[key]

    def ephemeral(self, message: str, duration: int = 2500) -> None:
        super().showMessage(message, duration)
