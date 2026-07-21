from typing import Self, TypedDict, Unpack
from weakref import ref

from PySide6.QtCore import QObject, QRectF
from PySide6.QtGui import QColor, QPaintDevice, QPainter, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import QWidget

from scriptwrite.types import QtValueType
from scriptwrite.widgets.descriptors import QtProperty


class Color:
    def __init__(self, color: QColor, parent: QObject | QtValueType | None = None, bind: str | None = None) -> None:
        self._proxy = color

        self._parent: ref[QObject | QtValueType] | None = None
        self._bind: str | None = None

        if parent and bind:
            self.bind(parent, bind)

    def bind(self, parent: QObject | QtValueType, bind: str) -> None:
        self._parent = ref(parent) if parent else None
        self._bind = bind

    @classmethod
    def from_hex(cls, hex: str, *, parent: QObject | QtValueType | None = None, bind: str | None = None) -> Self:
        color = QColor.fromString(f"#{hex.removeprefix('#')}")
        return cls(color, parent=parent, bind=bind)

    @classmethod
    def from_rgb(
        cls,
        r: int,
        g: int,
        b: int,
        a: int = 255,
        *,
        parent: QObject | QtValueType | None = None,
        bind: str | None = None,
    ) -> Self:
        color = QColor(r, g, b, a)
        return cls(color, parent=parent, bind=bind)

    def _stative_set(self, key: str, value: int) -> None:
        getattr(self._proxy, key)(value)

        if self._parent is not None and (p := self._parent()) is not None and self._bind is not None:
            setattr(p, self._bind, self._proxy)

    @property
    def red(self) -> int:
        return self._proxy.red()

    @red.setter
    def red(self, value: int, /) -> None:
        self._stative_set("setRed", value)

    @property
    def green(self) -> int:
        return self._proxy.green()

    @green.setter
    def green(self, value: int, /) -> None:
        self._stative_set("setGreen", value)

    @property
    def blue(self) -> int:
        return self._proxy.blue()

    @blue.setter
    def blue(self, value: int, /) -> None:
        self._stative_set("setBlue", value)

    @property
    def alpha(self) -> int:
        return self._proxy.alpha()

    @alpha.setter
    def alpha(self, value: int, /) -> None:
        self._stative_set("setAlpha", value)

    def as_rgba(self) -> tuple[int, int, int, int]:
        return self.red, self.green, self.blue, self.alpha

    def as_hex(self) -> str:
        format = QColor.NameFormat.HexRgb if self.alpha == 0xFF else QColor.NameFormat.HexArgb
        return self._proxy.name(format=format)

    def with_alpha(self, alpha: int) -> Self:
        return type(self).from_rgb(r=self.red, g=self.green, b=self.blue, a=alpha)

    def with_lightness_scale(self, factor: float) -> Self:
        if factor >= 1:
            color = self._proxy.lighter(round(100 * factor))
        else:
            color = self._proxy.darker(round(100 / factor))

        return type(self)(color)


class TextStyleParams(TypedDict, total=False):
    fg: int | str | QColor | Color | None
    bg: int | str | QColor | Color | None
    bold: bool
    italic: bool
    underline: bool


class TextStyle(QTextCharFormat):
    italic: QtProperty[bool] = QtProperty("fontItalic")
    underline: QtProperty[bool] = QtProperty("fontUnderline")

    def __init__(self, **kwargs: Unpack[TextStyleParams]) -> None:
        super().__init__()

        self._fg: Color | None = None
        self._bg: Color | None = None

        if fg := kwargs.get("fg"):
            self.fg = fg

        if bg := kwargs.get("bg"):
            self.bg = bg

        self.bold = kwargs.get("bold", False)
        self.italic = kwargs.get("italic", False)
        self.underline = kwargs.get("underline", False)

    def as_dict(self) -> TextStyleParams:
        return TextStyleParams(fg=self.fg, bg=self.bg, bold=self.bold, italic=self.italic, underline=self.underline)

    @property
    def fg(self) -> Color | None:
        return self._fg

    @fg.setter
    def fg(self, value: int | str | QColor | Color, /) -> None:
        if isinstance(value, (int, str)):
            value = QColor(value)

        if isinstance(value, QColor):
            value = Color(value)
        else:
            # copy to prevent shared mutation
            value = Color(QColor(value._proxy))

        value.bind(self, "fg")

        super().setForeground(value._proxy)
        self._fg = value

    @property
    def bg(self) -> Color | None:
        return self._bg

    @bg.setter
    def bg(self, value: int | str | QColor | Color, /) -> None:
        if isinstance(value, (int, str)):
            value = QColor(value)

        if isinstance(value, QColor):
            value = Color(value)
        else:
            # copy to prevent shared mutation
            value = Color(QColor(value._proxy))

        value.bind(self, "bg")

        super().setBackground(value._proxy)
        self._bg = value

    def dimmed(self, factor: float = 0.5) -> Self:
        if self.fg is None:
            raise ValueError("Cannot call `dimmed` on a style without a defined color.")

        a = round(factor * self.fg.alpha)
        return self.replace(fg=self.fg.with_alpha(a))

    @property
    def bold(self) -> bool:
        return super().fontWeight() == 700

    @bold.setter
    def bold(self, value: bool, /) -> None:
        super().setFontWeight(700 if value else 400)

    def replace(self, **kwargs: Unpack[TextStyleParams]) -> Self:
        return type(self)(**{**self.as_dict(), **kwargs})


class SyntaxHighlighter(QSyntaxHighlighter):
    block_state: QtProperty[int] = QtProperty("currentBlockState")

    @property
    def previous_block_state(self) -> int:
        return super().previousBlockState()

    def highlight_block(self, text: str) -> None:
        super().highlightBlock(text)

    def apply(self, style: TextStyle, start: int, stop: int) -> None:
        super().setFormat(start, stop - start, style)


def fill_rect(surface: QPaintDevice, x: float, y: float, width: float, height: float, color: Color) -> None:
    painter = QPainter(surface)
    painter.fillRect(QRectF(x, y, width, height), color._proxy)
    painter.end()


def set_font_size(widget: QWidget, size: int) -> None:
    font = widget.font()
    font.setPointSize(size)
    widget.setFont(font)
