

from io import StringIO
import re
from typing import assert_never, cast

from scriptwrite.config import ExportConfig
from scriptwrite.parser import Character, LineType, Script, TextRunType


def render_title_page(script: Script) -> str:
    return f"""\
Title: {script.title}
Author: {script.author}
Draft date: {script.published.strftime('%Y-%m-%d') if script.published else ''}
"""


def render_fountain(script: Script, *, config: ExportConfig) -> str:
    buffer = StringIO()

    buffer.write(render_title_page(script))

    last_type: LineType | None = None
    last_speaker: Character | None = None
    for line in script.lines:
        match line.type:
            case LineType.SPOKEN | LineType.LISTENER:
                if line.type == LineType.SPOKEN:
                    speaker = cast(Character, line.speaker)
                    name = speaker.name.upper()
                else:
                    speaker = script.listener
                    name = script.listener.name.upper() or "LISTENER"

                if re.search(r"[A-Z]", name) is None:
                    # Fountain requires a character name to contain at least one letter character
                    # though it can be forced via the @ character
                    name = f"@{name}"

                if last_type == line.type and last_speaker == speaker:
                    # If the previous line of the script was also this speaker,
                    # then we can render it as one continuous block,
                    # which means that we do not need to emit the character name.
                    pass
                else:
                    # We need to emit the character name.
                    buffer.write("\n\n")
                    if last_speaker == speaker:
                        buffer.write(f"{name} (CONT.)\n")
                    else:
                        buffer.write(f"{name}\n")

                for run in line.text_runs:
                    match run.type:
                        case TextRunType.NORMAL:
                            buffer.write(run.text)

                        case TextRunType.DIRECTIVE:
                            if buffer.getvalue()[-1] != "\n":
                                # We're already in the middle of a line, so we need to get to a new line
                                buffer.write("\n")

                            buffer.write(f"({run.text})\n")

                        case TextRunType.HIGHLIGHT:
                            # best we can do is bold it
                            buffer.write(f"**{run.text}**")

                        case TextRunType.EMPHASIS:
                            buffer.write(f"*{run.text}*")

            case LineType.CUE:
                text = " ".join(run.text for run in line.text_runs)
                buffer.write(f"\n\n{text}\n")

            case LineType.COMMENT:
                pass

            case _:
                assert_never(line.type)

    return buffer.getvalue()
