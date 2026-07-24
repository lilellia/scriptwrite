from typing import assert_never, cast

from PySide6.QtGui import QTextCursor, QTextDocument

from scriptwrite.parser import Character, Line, LineType, Script, TextRunType
from scriptwrite.widgets.display import Color, TextStyle
from scriptwrite.widgets.text import BlockFormat, TextBlock


def render_header(script: Script, cursor: QTextCursor) -> None:
    with TextBlock(cursor) as block:
        block.format = BlockFormat(cursor.block(), margin_top=8, margin_bottom=12, heading=1)
        block.write(script.title, TextStyle(bold=True))

    with TextBlock(cursor) as block:
        block.format = BlockFormat(cursor.block(), margin_top=8, margin_bottom=12, heading=2)
        block.write(script.author, TextStyle(bold=True))


def render_dialogue(line: Line, cursor: QTextCursor) -> None:

    metadata = dict(source_line=line.index, type=line.type, character=line.speaker)

    with TextBlock(cursor, **metadata) as block:
        block.format = BlockFormat(cursor.block(), margin_top=8, margin_bottom=8)
        color = cast(Character, line.speaker).colour

        for run in line.text_runs:
            match run.type:
                case TextRunType.NORMAL:
                    style = TextStyle(fg=color, bold=True)
                    block.write(run.text, style)

                case TextRunType.DIRECTIVE:
                    style = TextStyle(fg=color, italic=True)
                    block.write(f"({run.text})", style)

                case TextRunType.HIGHLIGHT:
                    style = TextStyle(fg=color, bg=color.with_alpha(0x40), bold=True)
                    block.write(run.text, style)

                case TextRunType.EMPHASIS:
                    style = TextStyle(fg=color, bold=True, underline=True)
                    block.write(run.text, style)


def render_listener(line: Line, cursor: QTextCursor) -> None:

    metadata = dict(source_line=line.index, type=line.type, character=None)

    with TextBlock(cursor, **metadata) as block:
        block.format = BlockFormat(cursor.block(), margin_top=8, margin_bottom=8)
        color = Color.from_rgb(153, 153, 153)

        normal = TextStyle(fg=color, italic=True, underline=False)
        emph = TextStyle(fg=color, italic=True, underline=True)

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


def render_cue(line: Line, cursor: QTextCursor) -> None:

    metadata = dict(source_line=line.index, type=line.type, character=None)

    with TextBlock(cursor, **metadata) as block:
        block.format = BlockFormat(cursor.block(), margin_top=8, margin_bottom=8)
        color = Color.from_rgb(89, 89, 89)

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


def render_comment(line: Line, cursor: QTextCursor) -> None:

    metadata = dict(source_line=line.index, type=line.type, character=None)

    with TextBlock(cursor, **metadata) as block:
        block.format = BlockFormat(cursor.block(), margin_top=8, margin_bottom=8)
        color = Color.from_rgb(166, 133, 150)

        normal = TextStyle(fg=color, italic=True, underline=False)
        emph = TextStyle(fg=color, italic=True, underline=True)

        block.write("//\N{NO-BREAK SPACE}", normal)

        for run in line.text_runs:
            match run.type:
                case TextRunType.EMPHASIS:
                    block.write(run.text, emph)

                case _:
                    block.write(run.text, normal)


def render_blocks(script: Script, into: QTextDocument) -> None:
    cursor = QTextCursor(into)

    render_header(script, cursor)

    for line in script.lines:
        match line.type:
            case LineType.SPOKEN:
                render_dialogue(line, cursor)

            case LineType.LISTENER:
                render_listener(line, cursor)

            case LineType.CUE:
                render_cue(line, cursor)

            case LineType.COMMENT:
                render_comment(line, cursor)

            case _:
                assert_never(line.type)
