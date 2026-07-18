from typing import Literal

from PySide6.QtWidgets import QFrame

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
