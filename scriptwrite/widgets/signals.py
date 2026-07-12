from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Generic, overload, Protocol, runtime_checkable, Self, TypeAlias, TypeVar
from weakref import ref, WeakKeyDictionary, WeakMethod

from PySide6.QtWidgets import QWidget

VoidFn = TypeVar("VoidFn", bound=Callable[..., None])
Q = TypeVar("Q", bound=QWidget)

F: TypeAlias = Callable[[], None]
Slot: TypeAlias = Callable[..., None]
WeakCallable: TypeAlias = WeakMethod[VoidFn] | ref[VoidFn]


@runtime_checkable
class QtSignal(Protocol):
    def connect(self, slot: Slot) -> Any: ...
    def disconnect(self, slot: Slot) -> Any: ...


@dataclass(slots=True, frozen=True)
class _WeakSlotPointer:
    weak_function: WeakCallable[F]


@dataclass(slots=True, frozen=True)
class _WeakSlotInfo:
    weak_instance: ref[QWidget]
    method: str


class WeakSlot:
    def __init__(self, f: F) -> None:
        self._context: _WeakSlotPointer | _WeakSlotInfo

        if (instance := getattr(f, "__self__", None)) is not None:
            if hasattr(f, "__func__"):
                # Python bound method
                self._context = _WeakSlotPointer(weak_function=WeakMethod(f))
            else:
                # C-extension / PySide method
                self._context = _WeakSlotInfo(weak_instance=ref(instance), method=f.__name__)
        else:
            # normal Python function
            self._context = _WeakSlotPointer(weak_function=ref(f))

    def _get_function(self) -> F | None:
        match self._context:
            case _WeakSlotPointer(weak_function):
                return weak_function()
            case _WeakSlotInfo(weak_instance, method):
                if obj := weak_instance():
                    return getattr(obj, method, None)

    def __call__(self, *_: Any, **__: Any) -> None:
        if f := self._get_function():
            f()


class QtSignalProperty(Generic[Q]):
    def __init__(self, signal_name: str) -> None:
        self.signal_name = signal_name
        self._slots: WeakKeyDictionary[Q, WeakSlot] = WeakKeyDictionary()

    @overload
    def __get__(self, instance: Q, owner: type[Q], /) -> F | None: ...

    @overload
    def __get__(self, instance: None, owner: type[Q], /) -> Self: ...

    def __get__(self, instance: Q | None, owner: type[Q] | None, /) -> Self | F | None:
        if instance is None:
            return self

        if (slot := self._slots.get(instance)) is not None:
            return slot()

    def __set__(self, instance: Q, callback: F | None, /) -> None:
        try:
            signal = getattr(instance, self.signal_name)
        except AttributeError:
            raise AttributeError(f"{type(instance).__name__} object has no signal Qt::{self.signal_name}")
        else:
            if not isinstance(signal, QtSignal):
                raise ValueError(f"{instance!r}.{self.signal_name} is not a Qt signal object")

        if (previous := self._slots.pop(instance, None)) is not None:
            with suppress(TypeError, RuntimeError):
                signal.disconnect(previous)

        if callback is not None:
            slot = WeakSlot(callback)

            signal.connect(slot)
            self._slots[instance] = slot
