from collections.abc import Mapping
from typing import Literal

from PySide6.QtWidgets import QFrame, QTabWidget, QWidget

from scriptwrite.widgets.descriptors import QtEnum, QtProperty


class Frame(QFrame):
    autofill_bg: QtProperty[bool] = QtProperty("autoFillBackground")
    frame_shape: QtEnum[Literal["none", "box", "panel", "styled-panel", "hline", "vline", "win-panel"]] = QtEnum(
        "frameShape",
        {
            "none": QFrame.Shape.NoFrame,
            "box": QFrame.Shape.Box,
            "panel": QFrame.Shape.Panel,
            "styled-panel": QFrame.Shape.StyledPanel,
            "hline": QFrame.Shape.HLine,
            "vline": QFrame.Shape.VLine,
            "win-panel": QFrame.Shape.WinPanel,
        },
    )
    frame_shadow: QtEnum[Literal["none", "raised", "sunken"]] = QtEnum(
        "frameShadow", {"none": QFrame.Shadow.Plain, "sunken": QFrame.Shadow.Sunken, "raised": QFrame.Shadow.Raised}
    )


class Tabbed(QTabWidget):
    tab_shape: QtEnum[Literal["rounded", "triangular"]] = QtEnum(
        "tabShape", {"rounded": QTabWidget.TabShape.Rounded, "triangular": QTabWidget.TabShape.Triangular}
    )

    def __init__(
        self,
        parent: QWidget | None,
        tabs: Mapping[str, QWidget] | None = None,
        *,
        tab_shape: Literal["rounded", "triangular"] = "rounded",
    ) -> None:
        super().__init__(parent)
        self._tabs: dict[str, QWidget] = {}

        for label, tab in (tabs or {}).items():
            self.add(label, tab)

        self.tab_shape = tab_shape

    def add(self, label: str, tab: QWidget) -> None:
        if label in self._tabs:
            return

        super().addTab(tab, label)
        self._tabs[label] = tab

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(self._tabs.keys())

    @property
    def current_index(self) -> int:
        return super().currentIndex()

    @current_index.setter
    def current_index(self, value: int, /) -> None:
        super().setCurrentIndex(value)

    @property
    def current_label(self) -> str:
        return self.labels[self.current_index]

    @current_label.setter
    def current_label(self, value: str, /) -> None:
        i = self.labels.index(value)
        self.current_index = i

    @property
    def current_tab(self) -> QWidget:
        return super().currentWidget()

    @current_tab.setter
    def current_tab(self, value: QWidget, /) -> None:
        super().setCurrentWidget(value)
