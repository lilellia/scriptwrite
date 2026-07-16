from functools import partial
import sys
from typing import Literal, Protocol

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtWidgets import QMainWindow

from scriptwrite.widgets.actions import Shortcut
from scriptwrite.widgets.components import Toolbar, ToolbarActionGroup, ToolButton
from scriptwrite.widgets.layouts import Box
from scriptwrite.widgets.text import Entry

ButtonLabel = Literal[
    "find-next", "find-previous", "use-regex", "case-sensitive", "replace-one", "replace-all", "close"
]


class FindFunction(Protocol):
    def __call__(self, needle: str, forward: bool, use_regex: bool, case_sensitive: bool) -> None: ...


class ReplaceFunction(Protocol):
    def __call__(
        self, needle: str, replacement: str, replace_all: bool, use_regex: bool, case_sensitive: bool
    ) -> None: ...


class FindToolBar(Toolbar):
    def __init__(self, parent: QMainWindow, find: FindFunction, replace: ReplaceFunction):
        super().__init__(parent)
        self._find_callback = find
        self._replace_callback = replace

        self._buttons: dict[ButtonLabel, ToolButton] = {}

        _find_prev = partial(self.find_impl, f=find, forward=False)
        _find_next = partial(self.find_impl, f=find, forward=True)
        _replace_one = partial(self.replace_impl, r=replace, replace_all=False)
        _replace_all = partial(self.replace_impl, r=replace, replace_all=True)

        with Box(self, direction="vertical") as box:
            with Box(box, direction="horizontal") as row1:
                self.search_input = row1.add(Entry(self, placeholderText="Find..."))
                self.search_input.width_ = 200
                self.search_input.on_change = _find_next

                self._buttons["find-previous"] = row1.add(
                    self.add_action("«", tooltip="Find Previous", callback=_find_prev)
                )

                self._buttons["find-next"] = row1.add(self.add_action("»", tooltip="Find Next", callback=_find_next))

                self._buttons["case-sensitive"] = row1.add(
                    self.add_action("Aa", tooltip="Case Sensitive", checkable=True)
                )

                self._buttons["use-regex"] = row1.add(
                    self.add_action(".*", tooltip="Use Regex Patterns", checkable=True)
                )

                self._buttons["close"] = row1.add(self.add_action("×", tooltip="Close Toolbar", callback=self.hide))

            with Box(box, direction="horizontal") as row2:
                self.replace_input = row2.add(Entry(self, placeholderText="Replace..."))
                self.replace_input.width_ = 200

                self._buttons["replace-one"] = row2.add(
                    self.add_action("R1", tooltip="Replace Next", callback=_replace_one)
                )

                self._buttons["replace-all"] = row2.add(
                    self.add_action("R*", tooltip="Replace All", callback=_replace_all)
                )

                row2.add_stretch()

        ToolbarActionGroup(*self._buttons.values()).sync_widths()
        self.force_minimal_size()
        # allow Esc to close the toolbar
        # as long as it (or its children) are focused
        self._escape = Shortcut("Escape", self, callback=self.hide, scope="contained")

    @property
    def needle(self) -> str:
        return self.search_input.content

    @property
    def replacement(self) -> str:
        return self.replace_input.content

    @property
    def use_regex(self) -> bool:
        return self._buttons["use-regex"].checked

    @property
    def case_sensitive(self) -> bool:
        return self._buttons["case-sensitive"].checked

    def find_impl(self, f: FindFunction, forward: bool) -> None:
        f(needle=self.needle, forward=forward, use_regex=self.use_regex, case_sensitive=self.case_sensitive)

    def replace_impl(self, r: ReplaceFunction, replace_all: bool) -> None:
        r(
            needle=self.needle,
            replacement=self.replacement,
            replace_all=replace_all,
            use_regex=self.use_regex,
            case_sensitive=self.case_sensitive,
        )

    @override
    def toggle(self) -> None:
        super().toggle()

        if self.is_visible:
            self.search_input.setFocus()
            self.search_input.selectAll()
