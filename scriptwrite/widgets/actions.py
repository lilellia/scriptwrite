from collections.abc import Iterable
from typing import cast, Literal, Self

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import QToolButton, QWidget

from scriptwrite.types import F
from scriptwrite.widgets.descriptors import QtEnum, QtProperty
from scriptwrite.widgets.signals import QtSignalProperty


class Action(QAction):
    callback: QtSignalProperty = QtSignalProperty(signal_name="triggered")
    on_toggle: QtSignalProperty = QtSignalProperty(signal_name="toggled")
    checked: QtProperty[bool] = QtProperty(getter="isChecked", setter="setChecked")
    checkable: QtProperty[bool] = QtProperty(getter="isCheckable", setter="setCheckable")

    def __init__(
        self,
        text: str,
        parent: QWidget | None = None,
        *,
        callback: F | None = None,
        tooltip: str | None = None,
        shortcut: str | Iterable[str] | None = None,
        checkable: bool = False,
    ) -> None:
        kwargs = {}

        if tooltip:
            kwargs["toolTip"] = tooltip

        self._name = text
        super().__init__(text, parent, checkable=checkable, **kwargs)
        self.callback = callback

        if shortcut is not None:
            if isinstance(shortcut, str):
                self.keys = (shortcut,)
            else:
                self.keys = shortcut

    @property
    def keys(self) -> list[str]:
        return [k.toString(QKeySequence.SequenceFormat.NativeText) for k in super().shortcuts()]

    @keys.setter
    def keys(self, value: Iterable[str], /) -> None:
        super().setShortcuts([QKeySequence(k) for k in value])

        s = ", ".join(self.keys)
        super().setText(f"{self._name}\t{s}")

    def bind(
        self,
        target: QWidget | None = None,
    ) -> Self:
        if target is None:
            if (p := super().parent()) is None:
                raise ValueError("Action is not bindable without specified target.")

            target = cast(QWidget, p)

        target.addAction(self)
        return self

    def toggle(self) -> None:
        if self.checkable:
            self.checked = not self.checked


class Shortcut(QShortcut):
    callback: QtSignalProperty = QtSignalProperty("activated")
    scope: QtEnum[Literal["application", "window", "widget", "contained"]] = QtEnum(
        "context",
        {
            "application": Qt.ShortcutContext.ApplicationShortcut,
            "window": Qt.ShortcutContext.WindowShortcut,
            "widget": Qt.ShortcutContext.WidgetShortcut,
            "contained": Qt.ShortcutContext.WidgetWithChildrenShortcut,
        },
    )

    def __init__(
        self,
        key: str,
        parent: QWidget,
        *,
        callback: F | None = None,
        scope: Literal["application", "window", "widget", "contained"] = "window",
    ) -> None:
        super().__init__(QKeySequence(key), parent)
        self.scope = scope
        self.callback = callback


class ToolButton(QToolButton):
    action: QtProperty[Action] = QtProperty("defaultAction")
    auto_raise: QtProperty[bool] = QtProperty("autoRaise")
    checkable: QtProperty[bool] = QtProperty(getter="isCheckable", setter="setCheckable")
    checked: QtProperty[bool] = QtProperty(getter="isChecked", setter="setChecked")
    button_style: QtEnum[Literal["follow", "icon", "text-beside-icon", "text", "text-under-icon"]] = QtEnum(
        "toolButtonStyle",
        {
            "follow": Qt.ToolButtonStyle.ToolButtonFollowStyle,
            "icon": Qt.ToolButtonStyle.ToolButtonIconOnly,
            "text-beside-icon": Qt.ToolButtonStyle.ToolButtonTextBesideIcon,
            "text": Qt.ToolButtonStyle.ToolButtonTextOnly,
            "text-under-icon": Qt.ToolButtonStyle.ToolButtonTextUnderIcon,
        },
    )

    def __init__(self, action: Action, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.action = action
        self.auto_raise = True
        self.checkable = action.checkable
        self.button_style = "text"
