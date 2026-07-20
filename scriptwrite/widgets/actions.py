from collections.abc import Iterable
from typing import cast, Generic, Literal, Self, TypeAlias, TypeVar

from PySide6.QtCore import (
    QEasingCurve,
    QLine,
    QLineF,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    QSizeF,
    Qt,
    QTime,
    QVariantAnimation,
)
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import QToolButton, QWidget

from scriptwrite.types import F
from scriptwrite.widgets.descriptors import QtEnum, QtProperty
from scriptwrite.widgets.signals import QtSignalProperty

V = TypeVar("V", bound=float | int | bool | QLine | QLineF | QPoint | QPointF | QRect | QRectF | QSize | QSizeF | QTime)
EaseFunction: TypeAlias = Literal[
    "linear",
    "in-quad",
    "out-quad",
    "in-out-quad",
    "out-in-quad",
    "in-cubic",
    "out-cubic",
    "in-out-cubic",
    "out-in-cubic",
    "in-quart",
    "out-quart",
    "in-out-quart",
    "out-in-quart",
    "in-quint",
    "out-quint",
    "in-out-quint",
    "out-in-quint",
    "in-sine",
    "out-sine",
    "in-out-sine",
    "out-in-sine",
    "in-expo",
    "out-expo",
    "in-out-expo",
    "out-in-expo",
    "in-circ",
    "out-circ",
    "in-out-circ",
    "out-in-circ",
    "in-elastic",
    "out-elastic",
    "in-out-elastic",
    "out-in-elastic",
    "in-back",
    "out-back",
    "in-out-back",
    "out-in-back",
    "in-bounce",
    "out-bounce",
    "in-out-bounce",
    "out-in-bounce",
]


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


class AnimatedAction(QVariantAnimation, Generic[V]):
    on_update: QtSignalProperty = QtSignalProperty("valueChanged")
    on_finish: QtSignalProperty = QtSignalProperty("finished")
    initial_value: QtProperty[V] = QtProperty("startValue")
    final_value: QtProperty[V] = QtProperty("endValue")
    length: QtProperty[int] = QtProperty("duration")
    ease: QtEnum[EaseFunction] = QtEnum(
        "easingCurve",
        {
            "linear": QEasingCurve.Type.Linear,
            "in-quad": QEasingCurve.Type.InQuad,
            "out-quad": QEasingCurve.Type.OutQuad,
            "in-out-quad": QEasingCurve.Type.InOutQuad,
            "out-in-quad": QEasingCurve.Type.OutInQuad,
            "in-cubic": QEasingCurve.Type.InCubic,
            "out-cubic": QEasingCurve.Type.OutCubic,
            "in-out-cubic": QEasingCurve.Type.InOutCubic,
            "out-in-cubic": QEasingCurve.Type.OutInCubic,
            "in-quart": QEasingCurve.Type.InQuart,
            "out-quart": QEasingCurve.Type.OutQuart,
            "in-out-quart": QEasingCurve.Type.InOutQuart,
            "out-in-quart": QEasingCurve.Type.OutInQuart,
            "in-quint": QEasingCurve.Type.InQuint,
            "out-quint": QEasingCurve.Type.OutQuint,
            "in-out-quint": QEasingCurve.Type.InOutQuint,
            "out-in-quint": QEasingCurve.Type.OutInQuint,
            "in-sine": QEasingCurve.Type.InSine,
            "out-sine": QEasingCurve.Type.OutSine,
            "in-out-sine": QEasingCurve.Type.InOutSine,
            "out-in-sine": QEasingCurve.Type.OutInSine,
            "in-expo": QEasingCurve.Type.InExpo,
            "out-expo": QEasingCurve.Type.OutExpo,
            "in-out-expo": QEasingCurve.Type.InOutExpo,
            "out-in-expo": QEasingCurve.Type.OutInExpo,
            "in-circ": QEasingCurve.Type.InCirc,
            "out-circ": QEasingCurve.Type.OutCirc,
            "in-out-circ": QEasingCurve.Type.InOutCirc,
            "out-in-circ": QEasingCurve.Type.OutInCirc,
            "in-elastic": QEasingCurve.Type.InElastic,
            "out-elastic": QEasingCurve.Type.OutElastic,
            "in-out-elastic": QEasingCurve.Type.InOutElastic,
            "out-in-elastic": QEasingCurve.Type.OutInElastic,
            "in-back": QEasingCurve.Type.InBack,
            "out-back": QEasingCurve.Type.OutBack,
            "in-out-back": QEasingCurve.Type.InOutBack,
            "out-in-back": QEasingCurve.Type.OutInBack,
            "in-bounce": QEasingCurve.Type.InBounce,
            "out-bounce": QEasingCurve.Type.OutBounce,
            "in-out-bounce": QEasingCurve.Type.InOutBounce,
            "out-in-bounce": QEasingCurve.Type.OutInBounce,
        },
    )

    def __init__(
        self,
        *,
        initial_value: V,
        final_value: V,
        length: int,
        ease: EaseFunction = "linear",
        on_update: F | None = None,
        on_finish: F | None = None,
    ) -> None:
        super().__init__()
        self.initial_value = initial_value
        self.final_value = final_value
        self.length = length
        self.ease = ease

        self.on_update = on_update
        self.on_finish = on_finish

    @property
    def value(self) -> V:
        return super().currentValue()
