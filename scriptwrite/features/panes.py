from enum import IntEnum
import re
import sys
from typing import Any, cast

from scriptwrite import renderers
from scriptwrite.log import logger
from scriptwrite.widgets import qre
from scriptwrite.widgets.display import SyntaxHighlighter, TextStyle
from scriptwrite.widgets.text import anchors_of, TextArea

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtGui import QTextBlock, QTextBlockUserData


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
    def highlight_yaml_header(self, text: str) -> None:
        style = TextStyle(fg="#FFFFFF").dimmed(0.4)

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
        if match := qre.search(r"\bcolou?r: ([0-9A-Fa-f]{6})\b", text):
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


class SourceLineData(QTextBlockUserData):
    def __init__(self, source_line: int) -> None:
        super().__init__()
        self.source_line = source_line


class PreviewPane(TextArea):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        super().setReadOnly(True)
        self.css = renderers.html.DEFAULT_CSS
        self._source_line_map: dict[int, QTextBlock] = {}

    @override
    def _set_html(self, s: str) -> None:
        super()._set_html(s)

        # and now inject source line numbers
        self._source_line_map.clear()
        pattern = re.compile(r"^data-source-line_eq_(\d+)$")
        for block in self.blocks():
            for fragment in type(self).fragments_of(block):
                for name in anchors_of(fragment):
                    if match := pattern.match(name):
                        source_line = int(match.group(1), 10)
                        self._source_line_map[source_line] = block
                        block.setUserData(SourceLineData(source_line))

    def get_current_source_line(self) -> int | None:
        """Return the line number of the source that points to the line containing the cursor."""
        line, _ = self._cursor.position

        block = cast(QTextBlock, self.get_block_at_line(line))

        if (data := block.userData()) is None:
            logger.debug(f"Scroll sync failure: preview line {block.text()!r} does not contain reference")
            return None

        if not isinstance(data, SourceLineData):
            logger.debug(f"Scroll sync failure: preview line {block.text()!r} does not contain source line data")
            return None

        return data.source_line

    def scroll_to_source_line(self, line: int) -> None:
        target = self._source_line_map.get(line, None)

        if target is None and (valid := [x for x in self._source_line_map.keys() if x <= line]):
            # scan backwards to find the closet line before this one
            target = self._source_line_map[max(valid)]

        if target:
            self.scroll_to_block(target, align=True)
