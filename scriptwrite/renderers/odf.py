from io import StringIO
import os.path
from pathlib import Path
import re
import shutil
from tempfile import NamedTemporaryFile
from typing import assert_never
from xml.sax.saxutils import escape
from zipfile import ZIP_STORED, ZipFile

from scriptwrite.config import ExportConfig
from scriptwrite.parser import Character, Line, LineType, Script, TextRunType
from scriptwrite.widgets.display import Color

MIMETYPE = "application/vnd.oasis.opendocument.text"

PAPER_SIZE = {"a4": {"width": "210mm", "height": "297mm"}, "letter": {"width": "8.5in", "height": "11in"}}


def clean_name(name: str) -> str:
    return re.sub(r"[<>& '\"]", "", name).lower()


def get_manifest(*, font: str | None = None) -> str:
    if font:
        p = Path(font)
        path = f"Fonts/{p.name}"
        spec = p.suffix.lstrip(".").lower()
        font_manifest = f"""<manifest:file-entry manifest:full-path="{path}" manifest:media-type="font/{spec}"/>"""
    else:
        font_manifest = ""

    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3">
      <manifest:file-entry manifest:full-path="/" manifest:version="1.3" manifest:media-type="application/vnd.oasis.opendocument.text"/>
      <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
      <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
      {font_manifest}
</manifest:manifest>
"""


def _get_par_style(
    name: str,
    *,
    color: Color,
    marginx: str,
    bold: bool,
    italic: bool,
    marginy: str = "4px",
    font_size: str | None = None,
    align: str | None = None,
    parent_style: str | None = None,
    font: str | None = None,
    master_page: str | None = None,
    force_break: bool = False,
) -> str:
    return f"""\
        <style:style
            style:name="{name}"
            style:family="paragraph"
            {f'style:parent-style-name="{parent_style}"' if parent_style else ""}
            {f'style:master-page-name="{master_page}"' if master_page else ""}
            >

            <style:paragraph-properties
                fo:margin-top="{marginy}"
                fo:margin-bottom="{marginy}"
                fo:margin-left="{marginx}"
                fo:margin-right="{marginx}"
                {f'fo:text-align="{align}"' if align else ""}
                {'fo:break-before="page"' if force_break else ""}
            />

            <style:text-properties
                fo:color="{color.as_hex()}"
                {'fo:font-weight="bold"' if bold else ""}
                {'fo:font-style="italic"' if italic else ""}
                {f'fo:font-size="{font_size}"' if font_size else ""}
                {f'style:font-name="{font}"' if font else ""}
                {f'style:font-name-asian="{font}"' if font else ""}
                {f'style:font-name-complex="{font}"' if font else ""}
            />

        </style:style>
"""


def _get_dialogue_style(character: Character) -> str:
    return f"""\
    <style:style
        style:name="scriptwrite-dialogue-{clean_name(character.name)}"
        style:family="paragraph"
        style:parent-style-name="scriptwrite-dialogue"
        >

        <style:text-properties
            fo:color="{character.colour.as_hex()}"
        />

    </style:style>
"""


def get_styles(script: Script, config: ExportConfig) -> str:
    base = f"{config.odf.font_size}pt"
    font_name = Path(config.odf.font_path).stem if config.odf.font_path else ""

    font = (
        f"""\
    <office:font-face-decls>

        <style:font-face style:name="{font_name}" svg:font-family="{font_name}">
            <svg:font-face-src>
                <svg:font-face-uri xlink:href="Fonts/{Path(config.odf.font_path).name}" xlink:type="simple"/>
            </svg:font-face-src>
        </style:font-face>

    </office:font-face-decls>
"""
        if config.odf.font_path
        else ""
    )

    par_styles = "\n".join(
        (
            # title
            _get_par_style(
                "scriptwrite-title",
                color=Color.from_rgb(0, 0, 0),
                marginx="0cm",
                marginy="0.5cm",
                bold=True,
                italic=False,
                font_size=f"{2 * config.odf.font_size}pt",
                align="center",
                font=font_name,
                master_page="FirstPage",
            ),
            # author
            _get_par_style(
                "scriptwrite-author",
                color=Color.from_rgb(0, 0, 0),
                marginx="0cm",
                marginy="0.3cm",
                bold=True,
                italic=False,
                font_size=f"{round(1.5 * config.odf.font_size)}pt",
                align="center",
                font=font_name,
            ),
            # tags
            _get_par_style(
                "scriptwrite-tags",
                color=Color.from_rgb(0, 0, 0),
                marginx="2cm",
                marginy="0.5cm",
                bold=False,
                italic=False,
                font_size=base,
                font=font_name,
            ),
            # stage directions
            _get_par_style(
                "scriptwrite-stagedir",
                color=Color.from_rgb(89, 89, 89),
                marginx="1.5cm",
                bold=False,
                italic=True,
                font_size=base,
                font=font_name,
            ),
            # listener dialogue
            _get_par_style(
                "scriptwrite-listener",
                color=Color.from_rgb(153, 153, 153),
                marginx="2.5cm",
                bold=False,
                italic=True,
                font_size=base,
                font=font_name,
            ),
            # dialogue base format
            _get_par_style(
                "scriptwrite-dialogue",
                color=Color.from_rgb(0, 0, 0),
                marginx="0cm",
                bold=True,
                italic=False,
                font_size=base,
                font=font_name,
            ),
            # comment lines
            _get_par_style(
                "scriptwrite-comment",
                color=Color.from_rgb(166, 133, 150),
                marginx="6cm",
                font_size=f"{int(config.odf.font_size * 0.8)}pt",
                bold=False,
                italic=True,
                font=font_name,
            ),
            _get_par_style(
                "_centre",
                color=Color.from_rgb(0, 0, 0),
                marginx="0pt",
                bold=False,
                italic=False,
                marginy="8px",
                align="center",
                font=font_name,
            ),
            _get_par_style(
                "_headfoot",
                color=Color.from_rgb(200, 200, 200),
                marginx="0pt",
                bold=False,
                italic=False,
                marginy="0px",
                align="right",
                font=font_name,
                font_size=f"{round(0.75 * config.odf.font_size)}pt",
            ),
            # character dialogue colour overrides
            *(_get_dialogue_style(character) for character in script.characters),
        )
    )

    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles
    xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
    xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
    xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
    xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    office:version="1.3">

    {font}

    <office:styles>
        {par_styles}
    </office:styles>

    <office:automatic-styles>
        <style:page-layout style:name="page-layout-1">
            <style:page-layout-properties
                fo:page-width="{PAPER_SIZE[config.odf.paper_size]["width"]}"
                fo:page-height="{PAPER_SIZE[config.odf.paper_size]["height"]}"
                fo:margin-top="{config.odf.margins}"
                fo:margin-bottom="{config.odf.margins}"
                fo:margin-left="{config.odf.margins}"
                fo:margin-right="{config.odf.margins}"
            />

            <style:header-style>
                <style:header-footer-properties fo:min-height="0cm" fo:margin-bottom="5mm" display="true" />
            </style:header-style>

            <style:footer-style>
                <style:header-footer-properties fo:min-height="0cm" fo:margin-top="5mm" display="true" />
            </style:footer-style>

        </style:page-layout>
    </office:automatic-styles>

    <office:master-styles>
        <style:master-page style:name="FirstPage" style:page-layout-name="page-layout-1" style:next-page-name="ScriptBody" />

        <style:master-page style:name="ScriptBody" style:page-layout-name="page-layout-1">
            <style:header><text:p text:style-name="_headfoot">{escape(script.title)}</text:p></style:header>
            <style:footer><text:p text:style-name="_headfoot">{escape(script.author)} - <text:page-number/></text:p></style:footer>
        </style:master-page>
    </office:master-styles>
</office:document-styles>
"""


def render_line(line: Line) -> str:
    match line.type:
        case LineType.SPOKEN:
            assert line.speaker is not None
            prefix = suffix = ""
            style = f"scriptwrite-dialogue-{clean_name(line.speaker.name)}"
        case LineType.LISTENER:
            prefix, suffix = "«\u00a0", "\u00a0»"
            style = "scriptwrite-listener"
        case LineType.CUE:
            prefix, suffix = "[", "]"
            style = "scriptwrite-stagedir"
        case LineType.COMMENT:
            return ""
            # prefix, suffix = "// ", ""
            # style = "scriptwrite-comment"
        case _:
            assert_never(line.type)

    buffer = StringIO()

    for run in line.text_runs:
        text = escape(run.text)
        match run.type:
            case TextRunType.NORMAL:
                buffer.write(text)

            case TextRunType.DIRECTIVE:
                buffer.write(f"""<text:span text:style-name="scriptwrite-directive">({text})</text:span>""")

            case TextRunType.HIGHLIGHT:
                buffer.write(f"""<text:span text:style-name="scriptwrite-highlight">{text}</text:span>""")

            case TextRunType.EMPHASIS:
                buffer.write(f"""<text:span text:style-name="scriptwrite-emphasis">{text}</text:span>""")

            case _:
                assert_never(run.type)

    return f"""<text:p text:style-name="{style}">{prefix}{buffer.getvalue()}{suffix}</text:p>"""


def get_character_bio(character: Character, words: int) -> str:
    return f"""\
<text:p text:style-name="scriptwrite-dialogue-{clean_name(character.name)}">
    {character.name}: <text:span text:style-name="scriptwrite-directive">({words:,} words) {character.summary}</text:span>
</text:p>
"""


def get_content(script: Script, config: ExportConfig) -> str:
    tags = " ".join(f"[{tag}]" for tag in script.tags)
    characters = " ".join(
        get_character_bio(character, script.word_counts[character]) for character in script.characters
    )
    lines = "\n".join(render_line(line) for line in script.lines)
    font_name = Path(config.odf.font_path).stem if config.odf.font_path else ""

    font = (
        f"""\
    <office:font-face-decls>

        <style:font-face style:name="{font_name}" svg:font-family="{font_name}">
            <svg:font-face-src>
                <svg:font-face-uri xlink:href="Fonts/{Path(config.odf.font_path).name}" xlink:type="simple"/>
            </svg:font-face-src>
        </style:font-face>

    </office:font-face-decls>
    """
        if config.odf.font_path
        else ""
    )

    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
    xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
    xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
    xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    office:version="1.3">

    {font}

    <office:automatic-styles>
        <style:style style:name="scriptwrite-directive" style:family="text">
            <style:text-properties fo:font-weight="normal" fo:font-style="italic"/>
        </style:style>

        <style:style style:name="scriptwrite-highlight" style:family="text">
            <style:text-properties fo:background-color="{Color.from_rgb(233, 218, 82).as_hex()}"/>
        </style:style>

        <style:style style:name="scriptwrite-emphasis" style:family="text">
            <style:text-properties style:text-underline-style="solid" style:text-underline-width="auto" style:text-underline-color="font-color"/>
        </style:style>


        <style:style style:name="_insert-page-break" style:family="paragraph" style:master-page-name="ScriptBody">
            <style:paragraph-properties fo:break-before="page"/>
        </style:style>

        <style:style style:name="_centre-break" style:family="paragraph" style:parent-style-name="_centre" style:master-page-name="ScriptBody">
            <style:paragraph-properties fo:break-before="page"/>
        </style:style>


    </office:automatic-styles>

    <office:body>
        <office:text>
            <text:p text:style-name="scriptwrite-title">{script.title}</text:p>
            <text:p text:style-name="scriptwrite-author">{script.author}</text:p>
            <text:p text:style-name="scriptwrite-tags">{tags}</text:p>
            <text:p text:style-name="scriptwrite-tags">{script.summary} ({script.total_spoken_words:,} words)</text:p>

            <text:p text:style-name="_centre-break">DRAMATIS PERSONÆ</text:p>
            {characters}

            <text:p />
            <text:p text:style-name="_centre">FORMATTING</text:p>
            <text:p text:style-name="scriptwrite-dialogue">
                spoken text, coloured by speaker,
                with <text:span text:style-name="scriptwrite-directive">(inline directives)</text:span>
                and <text:span text:style-name="scriptwrite-emphasis">emphasis</text:span>
            </text:p>
            <text:p text:style-name="scriptwrite-stagedir">
                [stage directions and/or sfx]
            </text:p>
            <text:p text:style-name="scriptwrite-listener">
                « example listener dialogue, not intended to be voiced »
            </text:p>

            <text:p text:style-name="_insert-page-break"/>
            {lines}
        </office:text>
    </office:body>
</office:document-content>
"""


def write_odt(script: Script, path: Path, config: ExportConfig) -> None:
    with NamedTemporaryFile(suffix=".zip", delete=False, delete_on_close=False) as f, ZipFile(f.name, mode="w") as z:
        z.writestr("mimetype", MIMETYPE, compress_type=ZIP_STORED)
        z.writestr("content.xml", get_content(script, config))
        z.writestr("styles.xml", get_styles(script, config))

        if config.odf.font_path:
            with open(config.odf.font_path, "rb") as g:
                z.writestr(f"Fonts/{os.path.basename(config.odf.font_path)}", g.read())

            manifest = get_manifest(font=config.odf.font_path)
        else:
            manifest = get_manifest()

        z.writestr("META-INF/manifest.xml", manifest)

    # perform an atomic write of the zip file to the target .odt file
    shutil.move(f.name, path)
