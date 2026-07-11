from collections.abc import Callable
from typing import Any, Generic, overload, Protocol, runtime_checkable, Self, TypeAlias, TypeVar
from weakref import WeakKeyDictionary

from PySide6.QtWidgets import QWidget

F: TypeAlias = Callable[[], None]
Q = TypeVar("Q", bound=QWidget)


@runtime_checkable
class QtSignal(Protocol):
    def connect(self, slot: Callable[..., None]) -> Any: ...
    def disconnect(self, slot: Callable[..., None]) -> Any: ...


class QtSignalProperty(Generic[Q]):
    def __init__(self, signal_name: str) -> None:
        self.signal_name = signal_name
        self._listeners: WeakKeyDictionary[Q, F] = WeakKeyDictionary()

    @overload
    def __get__(self, instance: Q, owner: type[Q], /) -> F | None: ...

    @overload
    def __get__(self, instance: None, owner: type[Q], /) -> Self: ...

    def __get__(self, instance: Q | None, owner: type[Q] | None, /) -> Self | F | None:
        if instance is None:
            return self

        return self._listeners.get(instance)

    def __set__(self, instance: Q | None, callback: F | None, /) -> None:
        if instance is None:
            return

        try:
            signal = getattr(instance, self.signal_name)
        except AttributeError:
            raise AttributeError(f"{type(instance).__name__} object has no signal Qt::{self.signal_name}")
        else:
            if not isinstance(signal, QtSignal):
                raise ValueError(f"{instance!r}.{self.signal_name} is not a Qt signal object")

        if (previous := self._listeners.pop(instance, None)) is not None:
            try:
                signal.disconnect(previous)
            except (TypeError, RuntimeError):
                pass

        if callback is not None:

            def f(*args: Any, **kwargs: Any) -> None:
                callback()

            signal.connect(f)
            self._listeners[instance] = f
