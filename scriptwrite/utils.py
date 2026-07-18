from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields, replace
import re
from typing import Any, ParamSpec, Protocol, TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

    C = TypeVar("C", bound=DataclassInstance)


P = ParamSpec("P")
R = TypeVar("R")


def load_dataclass(cls: type[C], data: Mapping[str, Any]) -> C:
    kwargs: dict[str, Any] = {}

    for f in fields(cls):
        if f.name not in data:
            continue

        converter = f.metadata.get("converter", lambda x: x)
        kwargs[f.name] = converter(data[f.name])

    return cls(**kwargs)


def discard(f: Callable[P, R]) -> Callable[P, None]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        f(*args, **kwargs)

    return wrapper


@dataclass(slots=True, frozen=True)
class FindResult:
    index: int
    num_matches: int
    match: re.Match[str]
    wraparound: bool


class CursorContext(Protocol):
    @property
    def index(self) -> int: ...

    @property
    def selected_range(self) -> tuple[int, int] | None: ...

    @property
    def selected_text(self) -> str: ...


def make_needle(text: str, use_regex: bool, case_sensitive: bool) -> re.Pattern[str]:
    flags = re.MULTILINE
    if not case_sensitive:
        flags |= re.IGNORECASE

    pattern = text if use_regex else re.escape(text)
    return re.compile(pattern, flags)


def _is_same_selection(match: re.Match[str], ctx: CursorContext) -> bool:
    if not ctx.selected_range:
        return False

    span = match.span()
    text = match.group(0)

    return span[0] == ctx.selected_range[0] and text == ctx.selected_text


def _find(
    matches: Sequence[re.Match[str]], filter: Callable[[int, int], bool], ctx: CursorContext, *, force: bool = False
) -> FindResult:
    i = 1
    for i, match in enumerate(matches, start=1):
        if not force and _is_same_selection(match, ctx):
            # we're sitting on a match and being asked to forcibly match beyond it
            continue

        if filter(*match.span()):
            return FindResult(index=i, num_matches=len(matches), match=match, wraparound=False)
    else:
        # there were no matches after the cursor, so wrap around
        return FindResult(index=1, num_matches=len(matches), match=matches[0], wraparound=True)


def find_text(
    needle: re.Pattern[str], haystack: str, forward: bool, ctx: CursorContext, *, force: bool = False
) -> FindResult | None:
    if not needle or not haystack:
        return None

    if not (matches := list(needle.finditer(haystack))):
        return None

    if forward:
        return _find(matches, filter=lambda a, _: a >= ctx.index, ctx=ctx, force=force)
    else:
        # we're reversing the matches in order to look backwards
        # but that also means translating the index back
        # i --> N - i + 1
        result = _find(list(reversed(matches)), filter=lambda _, b: b <= ctx.index, ctx=ctx, force=force)
        return replace(result, index=result.num_matches - result.index + 1)
