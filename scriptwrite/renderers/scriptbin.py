from io import StringIO
from typing import assert_never

from scriptwrite.config import ExportConfig
from scriptwrite.parser import Character, Line, LineType, Script, TextRunType


def _emit_character(name: str, summary: str, *, label: str | None = None) -> str:
    if label:
        return f"- **{name} ({label})** — {summary}\n"

    return f"- **{name}** — {summary}\n"


def render_header(script: Script) -> str:
    buffer = StringIO()

    # Inclusivity Notes
    # TODO!

    # Characters
    buffer.write("## Characters\n")
    for char in script.characters:
        words = script.word_counts[char]
        buffer.write(_emit_character(char.name, f"({words:,} words) {char.summary}", label="speaker"))

    if script.listener.name:
        buffer.write(_emit_character(script.listener.name, script.listener.summary, label="listener"))
    else:
        buffer.write(_emit_character("unnamed listener", script.listener.summary))

    # Formatting Guide
    buffer.write("""\
## Formatting Guide

**spoken text**

**/emphasis/**

*(tone cue, suggested)*

> *[stage direction and/or sfx]*

> « example listener dialogue, not intended to be voiced »
""")

    buffer.write("--8<--\n")

    return buffer.getvalue()


def render_dialogue(line: Line, *, emit_name: bool) -> str:
    assert line.speaker is not None
    buffer = StringIO()

    if emit_name:
        buffer.write(f"({line.speaker.name.upper()})  \n")

    parts: list[str] = []

    for run in line.text_runs:
        match run.type:
            case TextRunType.NORMAL:
                parts.append(f"**{run.text.strip()}**")

            case TextRunType.DIRECTIVE:
                parts.append(f"*({run.text.strip()})*")

            case TextRunType.HIGHLIGHT:
                # scriptbin doesn't actually support this
                # so this will just render literally, but... :shrug:
                parts.append(f"=={run.text.strip()}==")

            case TextRunType.EMPHASIS:
                parts.append(f"/{run.text}/")

            case _:
                assert_never(run.type)

    buffer.write(" ".join(parts))
    return buffer.getvalue() + "\n\n"


def render_nondialogue(line: Line, *, prefix: str = "", suffix: str = "") -> str:
    buffer = StringIO()

    buffer.write(prefix)

    parts: list[str] = []
    for run in line.text_runs:
        match run.type:
            case TextRunType.NORMAL:
                parts.append(f"{run.text.strip()}")

            case TextRunType.DIRECTIVE:
                parts.append(f"({run.text.strip()})")

            case TextRunType.HIGHLIGHT:
                # scriptbin doesn't actually support this
                # so this will just render literally, but... :shrug:
                parts.append(f"=={run.text.strip()}==")

            case TextRunType.EMPHASIS:
                parts.append(f"/{run.text.strip()}/")

            case _:
                assert_never(run.type)

    buffer.write(" ".join(parts))
    buffer.write(suffix)

    return buffer.getvalue() + "\n\n"


def render_scriptbin(script: Script, *, config: ExportConfig) -> str:
    buffer = StringIO()

    buffer.write(render_header(script))

    last_speaker: Character | None = None
    for line in script.lines:
        match line.type:
            case LineType.SPOKEN:
                should_emit = not (last_speaker == line.speaker)
                buffer.write(render_dialogue(line, emit_name=should_emit))
                last_speaker = line.speaker

            case LineType.LISTENER:
                buffer.write(
                    render_nondialogue(
                        line,
                        prefix="> *\N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}\N{NO-BREAK SPACE}",
                        suffix="\N{NO-BREAK SPACE}\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}*"
                    )
                )

            case LineType.CUE:
                buffer.write(render_nondialogue(line, prefix="> *[", suffix="]*"))

            case LineType.COMMENT:
                pass

            case _:
                assert_never(line.type)

    return buffer.getvalue()
