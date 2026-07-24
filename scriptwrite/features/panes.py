from enum import IntEnum
import sys
from typing import Any, assert_never, cast, TypedDict

from PySide6.QtWidgets import QApplication

from scriptwrite import renderers
from scriptwrite.log import logger
from scriptwrite.parser import Character, LineType, Script
from scriptwrite.widgets import qre
from scriptwrite.widgets.display import Color, SyntaxHighlighter, TextStyle
from scriptwrite.widgets.text import BlockFormat, TextArea, UserData

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtGui import QFontMetricsF, QPalette, QTextBlock


class EditorPane(TextArea):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        super().setAcceptRichText(False)
        self._highlighter = Highlighter(self.doc)


class _BlockState(IntEnum):
    UNINITIALIZED = -1

    YAML_HEADER_OPEN = 1
    YAML_HEADER_CLOSED = 2

    HTML_COMMENT_OPEN = 4


class Highlighter(SyntaxHighlighter):
    @staticmethod
    def _text_color() -> Color:
        return Color(QApplication.palette().color(QPalette.ColorRole.Text))

    def highlight_yaml_header(self, text: str) -> None:
        style = TextStyle(fg=self._text_color()).dimmed(0.4)

        if self.previous_block_state == _BlockState.UNINITIALIZED:
            # first line of the file
            if text.strip() == "---":
                self.block_state = _BlockState.YAML_HEADER_OPEN
                self.apply(style, 0, len(text))
            else:
                # the first line wasn't a header opening, so there can be no header
                self.block_state = _BlockState.YAML_HEADER_CLOSED

        elif self.previous_block_state & _BlockState.YAML_HEADER_OPEN:
            self.block_state = _BlockState.YAML_HEADER_CLOSED if text.strip() == "---" else _BlockState.YAML_HEADER_OPEN
            self.apply(style, 0, len(text))

        else:
            self.block_state = _BlockState.YAML_HEADER_CLOSED

    def highlight_color_attribute(self, text: str) -> None:
        if match := qre.search(r"\bcolou?r: \"?([0-9A-Fa-f]{6})\"?", text):
            style = TextStyle(fg=f"#{match.group(1)}")
            self.apply(style, *match.span())

    def highlight_html_comment(self, text: str) -> None:
        style = TextStyle(fg="#FFFFFF").dimmed(0.15)

        if (state := self.previous_block_state) == _BlockState.UNINITIALIZED:
            state = 0

        if state & _BlockState.HTML_COMMENT_OPEN:
            if match := qre.search(r"-->", text):
                # there's a closing tag
                end = match.end()
                self.block_state &= ~_BlockState.HTML_COMMENT_OPEN
            else:
                end = len(text)
                self.block_state |= _BlockState.HTML_COMMENT_OPEN

            self.apply(style, 0, end)

        else:
            # there isn't already an open comment

            if match := qre.search(r"<!--", text):
                # there's an opening tag
                start = match.start()

                if match := qre.search(r"-->", text):
                    # there's also a closing tag
                    end = match.end()
                    self.block_state &= ~_BlockState.HTML_COMMENT_OPEN
                else:
                    end = len(text)
                    self.block_state |= _BlockState.HTML_COMMENT_OPEN

                self.apply(style, start, end)
            else:
                self.block_state &= ~_BlockState.HTML_COMMENT_OPEN

    @override
    def highlightBlock(self, text: str, /) -> None:
        self.highlight_yaml_header(text)
        self.highlight_html_comment(text)
        self.highlight_color_attribute(text)


class LineData(TypedDict, total=False):
    source_line: int
    type: LineType
    character: Character | None


class PreviewPane(TextArea):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        super().setReadOnly(True)
        self.css = renderers.html.DEFAULT_CSS
        self._source_line_map: dict[int, QTextBlock] = {}

    def write(self, script: Script) -> None:
        with self.transaction():
            self.doc.clear()
            renderers.block.render_blocks(script, self.doc)
        logger.debug("blocks written")
        self.update_source_line_map()
        self.update_block_formatting()

    def update_source_line_map(self) -> None:
        self._source_line_map.clear()
        for block in self.blocks():
            data = self.get_block_data(block)

            if (source := data.get("source_line")) is not None:
                self._source_line_map[source] = block

    def update_block_formatting(self) -> None:
        base_font_size = super().font().pointSizeF()
        ch = QFontMetricsF(super().font()).horizontalAdvance("0")

        with self.suppress_signals(), self.suppress_updates(), self.transaction():
            for block in self.blocks():
                data = self.get_block_data(block)
                fmt = BlockFormat(block)

                match data.get("type"):
                    case None:
                        match fmt.heading:
                            case 1:
                                fmt.font_size = base_font_size * 2
                            case 2:
                                fmt.font_size = base_font_size * 1.5

                    case LineType.LISTENER:
                        fmt.margin_left = 12 * ch
                        fmt.margin_right = 12 * ch

                    case LineType.CUE:
                        fmt.margin_left = 6 * ch
                        fmt.margin_right = 6 * ch

                    case LineType.COMMENT:
                        fmt.margin_left = 20 * ch
                        fmt.margin_right = 20 * ch
                        fmt.font_size = base_font_size * 0.8

                    case LineType.SPOKEN:
                        fmt.margin_left = 0
                        fmt.margin_right = 0

                    case _t:
                        assert_never(_t)

    @staticmethod
    def get_block_data(block: QTextBlock) -> LineData:
        if (data := block.userData()) and isinstance(data, UserData):
            return LineData(**data.kwargs)

        return LineData()

    def get_current_source_line(self) -> int | None:
        """Return the line number of the source that points to the line containing the cursor."""
        line, _ = self._cursor.position

        block = cast(QTextBlock, self.get_block_at_line(line))
        data = self.get_block_data(block)

        return data.get("source_line")

    def scroll_to_source_line(self, line: int) -> None:
        target = self._source_line_map.get(line, None)

        if target is None and (valid := [x for x in self._source_line_map.keys() if x <= line]):
            # scan backwards to find the closest line before this one
            target = self._source_line_map[max(valid)]

        if target is None:
            # try grabbing the first line after this one
            target = next(block for key, block in self._source_line_map.items() if key >= line)

        if target:
            self.scroll_to_block(target, align=True)
        else:
            logger.warning(f"Could not scroll to source line {line}. No valid target found.")
