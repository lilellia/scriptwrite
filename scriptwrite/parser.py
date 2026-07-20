from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import auto, Enum
from io import StringIO
from pathlib import Path
import re
from typing import Any, cast, NamedTuple

from niji.colors import parse_color_input, RGBColor
import ruamel.yaml

from scriptwrite.utils import load_dataclass

RUN_SPLIT_PATTERN = re.compile(r"\(.*?\)|\*.*?\*|==.*?==")


class Document(NamedTuple):
    header: str
    body: str
    offset: int


class TextRunType(Enum):
    NORMAL = auto()
    DIRECTIVE = auto()
    EMPHASIS = auto()
    HIGHLIGHT = auto()


@dataclass(slots=True, frozen=True)
class TextRun:
    type: TextRunType
    text: str


class LineType(Enum):
    SPOKEN = auto()
    LISTENER = auto()
    CUE = auto()
    COMMENT = auto()


@dataclass(slots=True, frozen=True)
class Character:
    name: str
    colour: RGBColor = field(default=RGBColor(0, 0, 0), metadata=dict(converter=parse_color_input))
    aliases: tuple[str, ...] = field(default_factory=tuple, metadata=dict(converter=tuple))
    summary: str = ""


@dataclass(slots=True, frozen=True)
class Line:
    index: int
    type: LineType
    speaker: Character | None
    text_runs: list[TextRun] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class Script:
    title: str
    author: str
    audience: list[str]
    summary: str
    series: str | None = None
    tags: list[str] = field(default_factory=list)
    published: datetime | None = None
    characters: list[Character] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    word_counts: dict[Character, int] = field(default_factory=dict)
    unspoken_words: int = 0

    @property
    def word_count_display(self) -> str:
        by_char = " | ".join(f"{char.name}: {words:,}" for char, words in self.word_counts.items())
        return f"{by_char} (total = {self.total_spoken_words:,} = {self.total_words:,} x {self.speech_density:.4f})"

    @property
    def total_spoken_words(self) -> int:
        return sum(self.word_counts.values())

    @property
    def total_words(self) -> int:
        return self.total_spoken_words + self.unspoken_words

    @property
    def speech_density(self) -> float:
        return self.total_spoken_words / self.total_words


def is_directive_run(text: str) -> bool:
    """
    Determine whether the run should be treated as a directive.
    Note that a return value of True does not mean it should be spoken,
    as it may be enclosed in an entirely unspoken line.
    """
    return re.fullmatch(r"\(.*?\)|\*.*?\*", text) is not None


def count_words(text: str, /) -> int:
    """Return the number of words in the given string."""
    words = re.findall(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ'~∼/-]+", text)
    return len(words)


def split_off_header(text: str) -> Document:
    if not text:
        return Document(header="", body="", offset=0)

    lines = text.splitlines()

    if lines[0] != "---":
        # document does not begin with a header
        return Document(header="", body=text, offset=0)

    buffer = StringIO()
    for i, line in enumerate(lines[1:], start=1):
        if line == "---":
            return Document(header=buffer.getvalue(), body="\n".join(lines[i + 1 :]), offset=i + 1)
        else:
            buffer.write(line + "\n")

    # there's no trailing --- to close the header, so everything is header
    return Document(header=buffer.getvalue(), body="", offset=len(lines))


def parse_header(text: str) -> dict[str, Any]:
    return cast(dict[str, Any], ruamel.yaml.YAML(typ="safe").load(text))


def identify_run(run_text: str) -> TextRun:
    if match := re.fullmatch(r"\((.*)\)", run_text):
        return TextRun(TextRunType.DIRECTIVE, match.group(1))

    if match := re.fullmatch(r"\*(.*)\*", run_text):
        return TextRun(TextRunType.EMPHASIS, match.group(1))

    if match := re.fullmatch(r"==(.*)==", run_text):
        return TextRun(TextRunType.HIGHLIGHT, match.group(1).lstrip("{").rstrip("}"))

    return TextRun(TextRunType.NORMAL, run_text)


def parse_cue_line(index: int, line: str) -> Line:
    # ex: "++This is a cue line."
    runs = [identify_run(r) for r in regex_partition(line.removeprefix("++"), RUN_SPLIT_PATTERN)]
    return Line(index, LineType.CUE, speaker=None, text_runs=runs)


def parse_listener_line(index: int, line: str) -> Line:
    # ex: "--This is a listener line."
    runs = [identify_run(r) for r in regex_partition(line.removeprefix("--"), RUN_SPLIT_PATTERN)]
    return Line(index, LineType.LISTENER, speaker=None, text_runs=runs)


def parse_spoken_line(index: int, line: str, previous_speaker: Character | None, characters: list[Character]) -> Line:
    # first, figure out if the line starts with a character name directive
    speaker = previous_speaker
    content = line
    for character in characters:
        if any(re.match(rf"{a}:", line) for a in (character.name, *character.aliases)):
            speaker = character
            content = re.split(r":\s*", line, maxsplit=1)[1]
            break

    runs = [identify_run(r) for r in regex_partition(content, RUN_SPLIT_PATTERN)]
    return Line(index, LineType.SPOKEN, speaker=speaker, text_runs=runs)


def regex_partition(text: str, pattern: str | re.Pattern[str]) -> list[str]:
    if isinstance(pattern, re.Pattern):
        pattern = pattern.pattern

    parts = re.split(f"({pattern})", text)
    return [part for part in parts if part]


def parse_text(content: str) -> Script:
    header_raw, body, offset = split_off_header(content)
    header = parse_header(header_raw)

    title = header.get("title", "")
    audience = header.get("audience", [])
    author = header.get("author", "")
    summary = header.get("summary", "")
    tags = header.get("audience", []) + header.get("tags", [])
    published = header.get("published", None)
    series = header.get("series", None)
    characters = [load_dataclass(Character, data) for data in header["characters"]]
    lines: list[Line] = []
    word_counts: dict[Character, int] = defaultdict(int)
    unspoken_words = 0

    previous_speaker: Character | None = None
    for index, line in enumerate(body.splitlines(), start=offset + 1):
        if not line.strip():
            continue

        if line.startswith("[//]"):
            content = line.removeprefix("[//]").strip()
            lines.append(Line(index, LineType.COMMENT, speaker=None, text_runs=[TextRun(TextRunType.NORMAL, content)]))

        elif line.startswith("++"):
            # cue line
            parsed = parse_cue_line(index, line)
            lines.append(parsed)
            unspoken_words += sum(count_words(r.text) for r in parsed.text_runs)

        elif line.startswith("--"):
            # listener dialogue line
            parsed = parse_listener_line(index, line)
            lines.append(parsed)
            unspoken_words += sum(count_words(r.text) for r in parsed.text_runs)
        else:
            # spoken line
            parsed = parse_spoken_line(index, line, previous_speaker, characters)

            lines.append(parsed)
            previous_speaker = lines[-1].speaker

            assert previous_speaker is not None

            word_counts[previous_speaker] += sum(
                count_words(r.text) for r in parsed.text_runs if r.type != TextRunType.DIRECTIVE
            )
            unspoken_words += sum(count_words(r.text) for r in parsed.text_runs if r.type == TextRunType.DIRECTIVE)

    return Script(
        title=title,
        author=author,
        audience=audience,
        summary=summary,
        tags=tags,
        series=series,
        published=published,
        characters=characters,
        lines=lines,
        word_counts=word_counts,
        unspoken_words=unspoken_words,
    )


def parse_script(filepath: Path, selector: int) -> Script:
    content = re.sub(r"==\{(.*?)/(.*?)\}==", lambda m: m.group(selector), filepath.read_text())

    # remove actual commented content
    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)

    content = content.rstrip("\u000a\u0000")
    return parse_text(content)
