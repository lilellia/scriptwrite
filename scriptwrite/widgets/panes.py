from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from html.parser import HTMLParser
from io import StringIO
import re
import sys
from typing import Any, cast, NamedTuple

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtGui import (
    QTextBlock,
    QTextBlockUserData,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextFragment,
)
from PySide6.QtWidgets import QTextEdit

from scriptwrite import renderers


class _HTMLInjector(HTMLParser):
    def __init__(self, buffer: StringIO) -> None:
        super().__init__()
        self._buffer = buffer

    @staticmethod
    def _make_attr_str(attrs: list[tuple[str, str | None]]) -> str:
        return "".join(f' {k}="{v}"' if v is not None else f" {k}" for k, v in attrs)

    def _inject(self, attrs: list[tuple[str, str | None]]) -> None:
        for k, v in attrs:
            if k.startswith("data-") and v is not None:
                # forcibly inject an anchor tag
                self._buffer.write(f'<a name="{k}_eq_{v}"></a>')

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._buffer.write(f"<{tag}{self._make_attr_str(attrs)}>")
        self._inject(attrs)

    @override
    def handle_endtag(self, tag: str) -> None:
        self._buffer.write(f"</{tag}>")

    @override
    def handle_data(self, data: str) -> None:
        self._buffer.write(data)

    @override
    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._buffer.write(f"<{tag}{self._make_attr_str(attrs)} />")
        self._inject(attrs)  # best we can do is just put the injected elements immediately after

    @override
    def handle_decl(self, decl: str) -> None:
        self._buffer.write(f"<!{decl}>")

    @override
    def handle_pi(self, data: str) -> None:
        self._buffer.write(f"<?{data}>")

    @classmethod
    def inject_into(cls, source: str) -> str:
        buffer = StringIO()
        instance = cls(buffer)
        instance.feed(source)
        return buffer.getvalue()


class CursorPosition(NamedTuple):
    line: int
    column: int


class TextEdit(QTextEdit):
    @property
    def content(self) -> str:
        return super().toPlainText()

    @content.setter
    def content(self, s: str, /) -> None:
        super().setPlainText(s)

    @property
    def html(self) -> str:
        return super().toHtml()

    @html.setter
    def html(self, s: str, /) -> None:
        # bring Qt kicking and screaming into the slightly-less-distant past
        s = _HTMLInjector.inject_into(s)
        super().setHtml(s)

    @property
    def doc(self) -> QTextDocument:
        return cast(QTextDocument, super().document())

    @property
    def cursor_position(self) -> CursorPosition:
        cur = super().textCursor()
        return CursorPosition(line=cur.blockNumber() + 1, column=cur.columnNumber() + 1)

    @cursor_position.setter
    def cursor_position(self, pos: Iterable[int], /) -> None:
        line, column = pos
        block = self.doc.findBlockByLineNumber(line - 1)

        if not block.isValid():
            return

        # clamp column to line length
        col = max(0, min(column - 1, len(block.text())))

        cur = super().textCursor()
        cur.setPosition(block.position() + col)
        super().setTextCursor(cur)
        super().ensureCursorVisible()

    def scroll_to_block(self, block: QTextBlock, *, align_top: bool = False) -> None:
        super().setTextCursor(QTextCursor(block))
        super().ensureCursorVisible()

        if align_top:
            y = self.doc.documentLayout().blockBoundingRect(block).top()
            super().verticalScrollBar().setValue(int(y))

    @property
    def font_size(self) -> int | None:
        """Return the editor's font size, in pt. If the system is using pixel sizing, return None."""
        if (size := super().font().pointSize()) <= 0:
            return None

        return size

    @contextmanager
    def suppress_signals(self) -> Iterator[None]:
        try:
            super().blockSignals(True)
            yield
        finally:
            super().blockSignals(False)

    @property
    def css(self) -> str:
        return self.doc.defaultStyleSheet()

    @css.setter
    def css(self, s: str, /) -> None:
        # QTextEdit doesn't support all of modern CSS
        # so we'll modify what we need to in order to get a reasonable translation
        _FLOAT_REGEX = "[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)"
        base_font_size = self.font_size or 10  # use 10pt as a default fo rmeasurement

        def _em_to_px(em: float) -> int:
            # 1 em     S pt     4 px
            #       x ------ x ------
            #          1 em     3 pt
            #
            # where S is the font-size (pt). Thus, 1em = 4S/3 px.
            return round(em * 4 * base_font_size / 3)

        # QTextEdit does not support ch as a unit, so we'll convert it to pt
        def _convert_ch(m: re.Match[str]) -> str:
            em = 0.5 * float(m.group(1))  # 1ch = 0.5em
            return f"{_em_to_px(em)}px"

        s = re.sub(rf"({_FLOAT_REGEX})\s*ch", _convert_ch, s)

        # QTextEdit also does not support em as a font size, so we'll fix that too

        def _font_size_em_to_px(m: re.Match[str]) -> str:
            em = float(m.group(1))
            return f"font-size: {_em_to_px(em)}px;"

        s = re.sub(rf"font-size:\s*({_FLOAT_REGEX})\s*em\s*;", _font_size_em_to_px, s)

        cast(QTextDocument, super().document()).setDefaultStyleSheet(s)

    def blocks(self) -> Iterator[QTextBlock]:
        """Return an iterator over the QTextBlock objects that define the document."""
        curr = self.doc.begin()
        while curr.isValid():
            yield curr
            curr = curr.next()

    @staticmethod
    def fragments_of(block: QTextBlock) -> Iterator[QTextFragment]:
        it = block.begin()
        while not it.atEnd():
            yield it.fragment()
            it += 1

    def fragments(self) -> Iterator[QTextFragment]:
        """Return an iterator over the QTextFragment objects that define the document."""
        for block in self.blocks():
            yield from type(self).fragments_of(block)

    def anchor_names(self) -> Iterator[str]:
        """Return an iterator over all names that define anchors within the document.
        An "anchor" is anything which can be scrolled to via scrollToAnchor.
        """
        for fragment in self.fragments():
            if (fmt := fragment.charFormat()).isAnchor():
                if names := fmt.property(QTextFormat.Property.AnchorName):
                    yield from names


class EditorPane(TextEdit):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        super().setAcceptRichText(False)


class SourceLineData(QTextBlockUserData):
    def __init__(self, source_line: int) -> None:
        super().__init__()
        self.source_line = source_line


class PreviewPane(TextEdit):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        super().setReadOnly(True)
        self.css = renderers.html.DEFAULT_CSS
        self._source_line_map: dict[int, QTextBlock] = {}

    @property
    def html(self) -> str:
        return super().html

    @html.setter
    def html(self, s: str, /) -> None:
        # forcibly call super().html.fset
        prop = getattr(super(__class__, type(self)), "html")
        prop.__set__(self, s)

        # and now inject source line numbers
        for block in self.blocks():
            for fragment in type(self).fragments_of(block):
                if (fmt := fragment.charFormat()).isAnchor():
                    for name in names if (names := fmt.property(QTextFormat.Property.AnchorName)) else []:
                        if match := re.match(r"data-source-line_eq_(\d+)", name):
                            source_line = int(match.group(1), 10)
                            self._source_line_map[source_line] = block
                            block.setUserData(SourceLineData(source_line))

    def scroll_to_source_line(self, line: int) -> None:
        target = self._source_line_map.get(line, None)

        if target is None and (valid := [x for x in self._source_line_map.keys() if x <= line]):
            # scan backwards to find the closet line before this one
            target = self._source_line_map[max(valid)]

        if target:
            self.scroll_to_block(target, align_top=True)
