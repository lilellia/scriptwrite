from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, cast

from PySide6.QtWidgets import QMainWindow, QMenu, QMenuBar

from scriptwrite.types import F
from scriptwrite.widgets.actions import Action


@dataclass(frozen=True, slots=True)
class MenuItemData:
    name: str
    callback: F | None
    shortcut: str | Iterable[str] | None = field(default=None, kw_only=True)


class MenuBar(QMenuBar):
    def __init__(
        self, parent: QMainWindow, *args: Any, menus: dict[str, Iterable[MenuItemData]] | None = None, **kwargs: Any
    ) -> None:
        super().__init__(parent, *args, **kwargs)
        self._parent = parent
        self._menus: dict[str, QMenu] = {}

        if menus:
            self._add_menus(menus)

        parent.setMenuBar(self)

    def _add_menu(self, name: str, items: Iterable[MenuItemData]):
        menu = cast(QMenu, super().addMenu(name))

        for item in items:
            if item.name == "---":
                menu.addSeparator()
                continue

            action = Action(item.name, self._parent, callback=item.callback, shortcut=item.shortcut).bind(self._parent)
            menu.addAction(action)

        self._menus[name] = menu

    def _add_menus(self, menus: dict[str, Iterable[MenuItemData]]) -> None:
        for name, items in menus.items():
            self._add_menu(name, items)
