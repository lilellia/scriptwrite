import re
import sys
from typing import Any, cast

from scriptwrite import renderers
from scriptwrite.log import logger
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
