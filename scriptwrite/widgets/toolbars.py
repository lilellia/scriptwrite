from functools import partial
from typing import cast, Protocol, Self

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow

from scriptwrite.widgets.components import Action, Entry, Toolbar


class FindFunction(Protocol):
    def __call__(self, forward: bool) -> None: ...


class ReplaceFunction(Protocol):
    def __call__(self, replace_all: bool) -> None: ...


class FindToolBar(Toolbar):
    def __init__(self, parent: QMainWindow, find: FindFunction, replace: ReplaceFunction):
        super().__init__("Find", parent, movable=False, floatable=False)
        self._find_callback = find
        self._replace_callback = replace

        # textbox
        self.search_input = Entry(self, placeholderText="Find...")
        self.search_input.setFixedWidth(200)
        self.search_input.on_change = partial(find, forward=True)
        self.add_widget(self.search_input)

        # buttons
        self.action_next = Action("›", callback=partial(find, forward=True)).bind(self)
        self.action_prev = Action("‹", callback=partial(find, forward=False)).bind(self)
        self.action_close = Action("×", callback=self.hide).bind(self)

    def toggle(self) -> None:
        if self.is_visible:
            super().hide()
        else:
            super().show()
            self.search_input.setFocus()
            self.search_input.selectAll()

    def bind(self) -> Self:
        parent = cast(QMainWindow, self.parent())

        parent.addToolBar(Qt.ToolBarArea.BottomToolBarArea, self)
        super().hide()
        return self
