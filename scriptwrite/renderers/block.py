from collections.abc import Callable
from typing import assert_never, cast

from PySide6.QtGui import QTextBlock, QTextCursor, QTextDocument

from scriptwrite.parser import Character, Line, LineType, Script, TextRunType
from scriptwrite.utils import cache
from scriptwrite.widgets.display import Color, Font, query_color, TextStyle
from scriptwrite.widgets.text import BlockFormat, TextBlock


@cache
def make_block_format(line_type: LineType) -> Callable[[QTextBlock, Font], BlockFormat]:
    match line_type:
        case LineType.SPOKEN:

            def _make(block: QTextBlock, font: Font) -> BlockFormat:
                return BlockFormat(block, margin_top=8, margin_bottom=8, margin_left=0, margin_right=0)

        case LineType.LISTENER:

            def _make(block: QTextBlock, font: Font) -> BlockFormat:
                indent = 12 * font.char_width
                return BlockFormat(block, margin_top=8, margin_bottom=8, margin_left=indent, margin_right=indent)

        case LineType.CUE:

            def _make(block: QTextBlock, font: Font) -> BlockFormat:
                indent = 6 * font.char_width
                return BlockFormat(block, margin_top=8, margin_bottom=8, margin_left=indent, margin_right=indent)

        case LineType.COMMENT:

            def _make(block: QTextBlock, font: Font) -> BlockFormat:
                indent = 20 * font.char_width
                return BlockFormat(
                    block,
                    margin_top=8,
                    margin_bottom=8,
                    margin_left=indent,
                    margin_right=indent,
                    font_size=0.8 * font.size,
                )

        case _t:
            assert_never(_t)

    return _make


def render_header(script: Script, cursor: QTextCursor, font: Font) -> None:
    # TITLE
    with TextBlock(cursor) as block:
        block.format = BlockFormat(cursor.block(), margin_top=8, margin_bottom=12, heading=1, font_size=font.size * 2)
        block.write(script.title, TextStyle(bold=True))

    # AUTHOR
    with TextBlock(cursor) as block:
        block.format = BlockFormat(cursor.block(), margin_top=8, margin_bottom=12, heading=2, font_size=font.size * 1.5)
        block.write(script.author, TextStyle(bold=True))

    # SUMMARY
    with TextBlock(cursor) as block:
        block.format = BlockFormat(cursor.block(), margin_top=8, margin_bottom=12)
        block.write(script.summary, TextStyle(italic=True))


@cache
def get_dialogue_style(fg: Color, run_type: TextRunType) -> TextStyle:
    match run_type:
        case TextRunType.NORMAL:
            return TextStyle(fg=fg, bold=True)

        case TextRunType.DIRECTIVE:
            return TextStyle(fg=fg, italic=True)

        case TextRunType.HIGHLIGHT:
            return TextStyle(fg=fg, bg=fg.with_alpha(0x40), bold=True)

        case TextRunType.EMPHASIS:
            return TextStyle(fg=fg, bold=True, underline=True)


def render_dialogue(line: Line, cursor: QTextCursor, font: Font) -> QTextBlock:

    metadata = dict(source_line=line.index, type=line.type, character=line.speaker)

    with TextBlock(cursor, **metadata) as block:
        block.format = make_block_format(LineType.SPOKEN)(cursor.block(), font)
        color = cast(Character, line.speaker).colour

        for run in line.text_runs:
            style = get_dialogue_style(color, run.type)
            text = f"({run.text})" if run.type is TextRunType.DIRECTIVE else run.text
            block.write(text, style)

    return cast(QTextBlock, block.__block__)


@cache
def get_listener_style(run_type: TextRunType) -> TextStyle:
    color = query_color("custom.dim-2")

    match run_type:
        case TextRunType.EMPHASIS:
            return TextStyle(fg=color, italic=True, underline=True)

        case _:
            return TextStyle(fg=color, italic=True, underline=False)


def render_listener(line: Line, cursor: QTextCursor, font: Font) -> QTextBlock:
    metadata = dict(source_line=line.index, type=line.type, character=None)

    with TextBlock(cursor, **metadata) as block:
        block.format = make_block_format(LineType.LISTENER)(cursor.block(), font)

        normal = get_listener_style(TextRunType.NORMAL)
        emph = get_listener_style(TextRunType.EMPHASIS)

        block.write("«\N{NO-BREAK SPACE}", normal)

        for run in line.text_runs:
            match run.type:
                case TextRunType.EMPHASIS:
                    block.write(run.text, emph)

                case TextRunType.DIRECTIVE:
                    block.write(f"({run.text})", normal)

                case _:
                    block.write(run.text, normal)

        block.write("\N{NO-BREAK SPACE}»", normal)

    return cast(QTextBlock, block.__block__)


def render_cue(line: Line, cursor: QTextCursor, font: Font) -> QTextBlock:

    metadata = dict(source_line=line.index, type=line.type, character=None)

    with TextBlock(cursor, **metadata) as block:
        block.format = make_block_format(LineType.CUE)(cursor.block(), font)
        color = query_color("custom.dim-3")

        normal = TextStyle(fg=color, italic=True, underline=False)
        emph = TextStyle(fg=color, italic=True, underline=True)

        block.write("[", normal)

        for run in line.text_runs:
            match run.type:
                case TextRunType.EMPHASIS:
                    block.write(run.text, emph)

                case _:
                    block.write(run.text, normal)

        block.write("]", normal)

    return cast(QTextBlock, block.__block__)


def render_comment(line: Line, cursor: QTextCursor, font: Font) -> QTextBlock:

    metadata = dict(source_line=line.index, type=line.type, character=None)

    with TextBlock(cursor, **metadata) as block:
        block.format = make_block_format(LineType.COMMENT)(cursor.block(), font)
        color = query_color("custom.dim-1")

        normal = TextStyle(fg=color, italic=True, underline=False)
        emph = TextStyle(fg=color, italic=True, underline=True)

        block.write("//\N{NO-BREAK SPACE}", normal)

        for run in line.text_runs:
            match run.type:
                case TextRunType.EMPHASIS:
                    block.write(run.text, emph)

                case _:
                    block.write(run.text, normal)

    return cast(QTextBlock, block.__block__)


def render_blocks(script: Script, into: QTextDocument, *, font: Font) -> dict[int, QTextBlock]:
    cursor = QTextCursor(into)

    source_line_map: dict[int, QTextBlock] = {}

    render_header(script, cursor, font=font)

    for line in script.lines:
        match line.type:
            case LineType.SPOKEN:
                block = render_dialogue(line, cursor, font=font)

            case LineType.LISTENER:
                block = render_listener(line, cursor, font=font)

            case LineType.CUE:
                block = render_cue(line, cursor, font=font)

            case LineType.COMMENT:
                block = render_comment(line, cursor, font=font)

            case _:
                assert_never(line.type)

        source_line_map[line.index] = block

    return source_line_map
