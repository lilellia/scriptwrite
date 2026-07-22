from __future__ import annotations

from abc import ABC, abstractmethod
import atexit
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import IntEnum
import inspect
import json
from os import PathLike
from pathlib import Path
from queue import Queue
import sys
from threading import Thread
from typing import Any, Protocol, TextIO

from typing_extensions import override

from scriptwrite.fs import APP_DIRS

DEFAULT_LOG_FORMAT = "{time:%Y-%m-%dT%H:%M:%S.%f %:z} | {level.name:<8} | {filename}:{line} | {message}"


class FilterFunc(Protocol):
    def __call__(self, record: Record) -> bool: ...


class FileSize(IntEnum):
    BYTE = 1
    KIBIBYTE = 1 << 10
    MEBIBYTE = 1 << 20
    GIBIBYTE = 1 << 30
    TEBIBYTE = 1 << 40


class Level(IntEnum):
    ALL = 0
    DEBUG = 10
    INFO = 20
    SUCCESS = 25
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    FATAL = 60


def _parse_log_level(level: Level | str) -> Level:
    match level:
        case Level():
            return level

        case str():
            try:
                return Level[level.upper()]
            except KeyError:
                raise ValueError(f"Unknown log level: {level!r}")

        case _:
            raise ValueError(f"Unknown log level: {level!r}")


@dataclass(slots=True, frozen=True)
class Record:
    level: Level
    name: str
    time: datetime
    message: str
    filename: str
    function: str
    line: int


class Handler(ABC):
    def __init__(self, level: Level | str, filter: FilterFunc | None = None):
        self._level: Level

        self.level = level
        self.filter = filter

    @abstractmethod
    def emit(self, record: Record, **extra: Any) -> None:
        pass

    def should_emit(self, record: Record) -> bool:
        if record.level < self.level:
            return False

        if self.filter is not None:
            return self.filter(record)

        return True

    @property
    def level(self) -> Level:
        return self._level

    @level.setter
    def level(self, value: Level | str, /) -> None:
        self._level = _parse_log_level(value)


class SinkHandler(Handler):
    def __init__(
        self,
        stream: TextIO,
        level: Level | str,
        format: str,
        filter: FilterFunc | None = None,
    ) -> None:
        super().__init__(level, filter)
        self.stream = stream
        self.format = format

    @override
    def emit(self, record: Record, **extra: Any) -> None:
        if not self.should_emit(record):
            return

        output = self.format.format(**asdict(record), **extra)

        self.stream.write(output + "\n")
        self.stream.flush()


class FileHandler(Handler):
    def __init__(
        self,
        path: str | PathLike[str],
        level: Level | str,
        filter: FilterFunc | None = None,
        rotation: int | None = None,
    ) -> None:
        super().__init__(level, filter)
        self.path = Path(path)
        self.rotation = rotation

    @override
    def emit(self, record: Record, **extra: Any) -> None:
        if not self.should_emit(record):
            return

        if self.rotation is not None and self.path.exists() and self.path.stat().st_size > self.rotation:
            self.rotate()

        data = {**asdict(record), **extra}

        # serialize the fields that aren't natively serializable
        data["time"] = format(data["time"], "%Y-%m-%dT%H:%M:%S.%f%:z")
        data["level"] = data["level"].name

        output = json.dumps(data)

        with open(self.path, "a") as f:
            f.write(output + "\n")
            f.flush()

    def rotate(self) -> None:
        dest = self.path.with_name(f"{self.path.name}.1")
        self.path.replace(dest)


class Logger:
    def __init__(self, name: str, level: Level | str = Level.ALL) -> None:
        self.name = name

        self._level: Level
        self.level = level

        self.handlers: dict[int, Handler] = {}

    @property
    def level(self) -> Level:
        return self._level

    @level.setter
    def level(self, value: Level | str, /) -> None:
        self._level = _parse_log_level(value)

    def get_open_id(self) -> int:
        if not self.handlers:
            return 0

        return max(self.handlers.keys()) + 1

    def add(
        self, stream: TextIO, level: Level | str, format: str = DEFAULT_LOG_FORMAT, filter: FilterFunc | None = None
    ) -> SinkHandler:
        handler = SinkHandler(stream, level, format, filter)
        self.handlers[self.get_open_id()] = handler
        return handler

    def add_file(
        self,
        path: str | PathLike[str],
        level: Level | str,
        filter: FilterFunc | None = None,
        rotation: int | None = None,
    ) -> FileHandler:
        handler = FileHandler(path, level, filter, rotation)
        self.handlers[self.get_open_id()] = handler
        return handler

    def __getitem__(self, id: int, /) -> Handler:
        return self.handlers[id]

    def __setitem__(self, id: int, handler: Handler, /) -> None:
        self.handlers[id] = handler

    def __delitem__(self, id: int, /) -> None:
        self.handlers.__delitem__(id)

    def remove(self, handler: Handler) -> None:
        self.handlers = {i: h for i, h in self.handlers.items() if h != handler}

    def debug(self, message: Any, **extra: Any) -> None:
        self.emit(Level.DEBUG, message, **extra)

    def info(self, message: Any, **extra: Any) -> None:
        self.emit(Level.INFO, message, **extra)

    def success(self, message: Any, **extra: Any) -> None:
        self.emit(Level.SUCCESS, message, **extra)

    def warning(self, message: Any, **extra: Any) -> None:
        self.emit(Level.WARNING, message, **extra)

    def error(self, message: Any, **extra: Any) -> None:
        self.emit(Level.ERROR, message, **extra)

    def critical(self, message: Any, **extra: Any) -> None:
        self.emit(Level.CRITICAL, message, **extra)

    def fatal(self, message: Any, **extra: Any) -> None:
        self.emit(Level.FATAL, message, **extra)
        sys.exit(1)

    # we use stacklevel=2 because
    # 0 = Logger.emit
    # 1 = Logger.info (example)
    # 2 = the function that called Logger.info
    def emit(self, level: Level, message: Any, *, stacklevel: int = 2, **extra: Any) -> None:
        if level < self.level:
            return

        caller = inspect.stack()[stacklevel]
        record = Record(
            level=level,
            name=self.name,
            time=datetime.now().astimezone(),
            message=str(message),
            filename=caller.filename,
            function=caller.function,
            line=caller.lineno,
        )

        for handler in self.handlers.values():
            _log_queue.put((handler, record, extra))


def _queue_handler(q: Queue) -> None:
    while True:
        handler, record, extra = q.get()

        if (handler, record, extra) == (None, None, None):
            # poison pill
            q.task_done()
            break

        try:
            handler.emit(record, **extra)
        except Exception as e:
            with suppress(Exception):
                if sys.__stderr__:
                    sys.__stderr__.write(f"Logging error: {e} | Lost record: {record}, {extra=}\n")
        finally:
            q.task_done()


_log_queue = Queue()
_log_queue_thread = Thread(target=_queue_handler, args=(_log_queue,), daemon=True)
_log_queue_thread.start()


@atexit.register
def flush_log_queue() -> None:
    _log_queue.put((None, None, None))
    _log_queue.join()


logger = Logger(name="scriptwrite")
terminal_logger = logger.add(sys.stderr, level=Level.DEBUG)
file_logger = logger.add_file(APP_DIRS.logs / "log.jsonl", level=Level.INFO, rotation=100 * FileSize.MEBIBYTE)
