from collections.abc import Iterator

from PySide6.QtCore import QRegularExpression, QRegularExpressionMatch

A = ASCII = 0x0008
I = IGNORECASE = 0x0001  # noqa: E741 (ambiguous name; I is chosen to align with re.I)
S = DOTALL = 0x0002
M = MULTILINE = 0x0004


def _interpret_flags(flags: int) -> QRegularExpression.PatternOption:
    if flags & ASCII:
        flags &= ~0x0040  # specifically disable the non-ascii flag that Qt uses
        flags &= ~ASCII  # and drop the ASCII flag that Qt doesn't know about
    else:
        flags |= 0x0040  # force the non-ASCII option

    return QRegularExpression.PatternOption(flags)


class QtMatch:
    def __init__(self, match: QRegularExpressionMatch) -> None:
        self._proxy = match

    def group(self, index: int | str) -> str:
        if self._proxy.hasCaptured(index):
            return self._proxy.captured(index)

        raise IndexError(f"no such group {index!r}")

    def start(self, group: int | str = 0) -> int:
        if (idx := self._proxy.capturedStart(group)) == -1:
            raise IndexError(f"no such group {group!r}")

        return idx

    def end(self, group: int | str = 0) -> int:
        if (idx := self._proxy.capturedEnd(group)) == -1:
            raise IndexError(f"no such group {group!r}")

        return idx

    def span(self, group: int | str = 0) -> tuple[int, int]:
        return self.start(group), self.end(group)

    def re(self) -> QRegularExpression:
        return self._proxy.regularExpression()

    def lastindex(self) -> int:
        return self._proxy.lastCapturedIndex()


def finditer(pattern: str, haystack: str, flags: int = 0x0040) -> Iterator[QtMatch]:
    iterator = QRegularExpression(pattern, options=_interpret_flags(flags)).globalMatch(haystack)

    while iterator.hasNext():
        yield QtMatch(iterator.next())


def search(pattern: str, haystack: str, flags: int = 0x0040) -> QtMatch | None:
    return next(finditer(pattern, haystack, flags), None)


def match(pattern: str, haystack: str, flags: int = 0x0040) -> QtMatch | None:
    return search(f"^{pattern.removeprefix('^')}", haystack, flags)


def fullmatch(pattern: str, haystack: str, flags: int = 0x0040) -> QtMatch | None:
    return search(f"^{pattern.removeprefix('^').removesuffix('$')}$", haystack, flags)
