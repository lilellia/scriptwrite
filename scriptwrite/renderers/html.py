from io import StringIO
from typing import Any, assert_never

from niji.colors import RGBColor

from scriptwrite.parser import Line, LineType, Script, TextRun, TextRunType

DEFAULT_CSS = """
.dialogue {
    font-weight: bold;
    margin: 8px inherit;
}

.directive {
    font-weight: normal;
    font-style: italic;
    margin: 0 0.2ch;
}

.listener {
    font-weight: normal;
    font-style: italic;
    color: rgb(153, 153, 153);
    margin: 8px 12ch;
}

.stagedir {
    font-weight: normal;
    font-style: italic;
    color: rgb(89, 89, 89);
    margin: 8px 6ch;
}

.comment {
    font-weight: normal;
    font-style: italic;
    font-size: 0.8em;
    color: rgb(166, 133, 150);
    margin: 8px 20ch;
}
"""


def as_hex(rgb: RGBColor) -> str:
    return f"#{rgb.red:02X}{rgb.green:02X}{rgb.blue:02X}"


def render_header(script: Script, *, inject_css: bool = True) -> str:
    return f"""\
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
  </head>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans:ital,wght@0,100..900;1,100..900&display=swap');

    body {{
        font-family: 'Noto Sans', sans-serif;
    }}

    {DEFAULT_CSS if inject_css else ""}
  </style>
  <body>
    <h1 class="script-title">{script.title}</h1>
    <h2>{script.author}</h2>
    <p>{script.summary}</p>
"""


def render_data_attrs(**attrs: Any) -> str:
    def make_kv_pair(key: str, value: Any) -> str:
        return f'data-{key.replace("_", "-")}="{value}"'

    return " ".join(make_kv_pair(key, value) for key, value in attrs.items())


def render_line(
    line: Line, *, clsname: str, prefix: str = "", suffix: str = "", color: RGBColor | None = None, **attrs: str
) -> str:
    buffer = StringIO()

    if prefix:
        buffer.write(prefix)

    for run in line.text_runs:
        match run.type:
            case TextRunType.NORMAL:
                buffer.write(f"""<span>{run.text}</span>""")

            case TextRunType.DIRECTIVE:
                buffer.write(f"""<span class="directive">({run.text})</span>""")

            case TextRunType.HIGHLIGHT:
                buffer.write(f"""<mark>{run.text}</mark>""")

            case TextRunType.EMPHASIS:
                buffer.write(f"""<u>{run.text}</u>""")

            case _:
                assert_never(run.type)

    if suffix:
        buffer.write(suffix)

    content = buffer.getvalue().replace("\\^\\_\\^", "^_^")
    data_attrs = render_data_attrs(source_line=line.index, **attrs)
    style = f'style="color: {as_hex(color)}"' if color else ""
    return f"""<p {data_attrs} class="{clsname}" {style}>{content}</p>"""


def make_comment_line(line: Line) -> Line:
    content = line.text_runs[0].text
    run = TextRun(TextRunType.NORMAL, content)
    return Line(line.index, LineType.COMMENT, speaker=None, text_runs=[run])


def render_html(script: Script, *, inject_css: bool = True) -> str:
    buffer = StringIO()

    buffer.write(render_header(script, inject_css=inject_css))

    for line in script.lines:
        match line.type:
            case LineType.SPOKEN:
                assert line.speaker is not None
                buffer.write(render_line(line, clsname="dialogue", color=line.speaker.colour))

            case LineType.LISTENER:
                buffer.write(render_line(line, clsname="listener", prefix="« ", suffix=" »"))

            case LineType.CUE:
                buffer.write(render_line(line, clsname="stagedir", prefix="[", suffix="]"))

            case LineType.COMMENT:
                buffer.write(render_line(make_comment_line(line), clsname="comment"))

            case _:
                assert_never(line.type)

    return buffer.getvalue()
