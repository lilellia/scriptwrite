from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from functools import partial
from typing import Any, Generic, overload, Protocol, runtime_checkable, Self, TypeAlias, TypeVar
from weakref import ref, WeakKeyDictionary, WeakMethod

from PySide6.QtWidgets import QWidget

from scriptwrite.types import F, Q

VoidFn = TypeVar("VoidFn", bound=Callable[..., None])
Slot: TypeAlias = Callable[..., None]
WeakCallable: TypeAlias = WeakMethod[VoidFn] | ref[VoidFn]


@runtime_checkable
class QtSignal(Protocol):
    def connect(self, slot: Slot) -> Any: ...
    def disconnect(self, slot: Slot) -> Any: ...


@dataclass(slots=True, frozen=True)
class _WeakSlotPointer:
    weak_function: WeakCallable[F]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


@dataclass(slots=True, frozen=True)
class _WeakSlotInfo:
    weak_instance: ref[QWidget]
    method: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


@dataclass(slots=True, frozen=True)
class _StrongSlotInfo:
    function: Slot
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


class WeakSlot:
    def __init__(self, f: F) -> None:
        self._context: _WeakSlotPointer | _WeakSlotInfo | _StrongSlotInfo

        if isinstance(f, partial):
            args: tuple[Any, ...] = f.args
            kwargs: dict[str, Any] = f.keywords
            f = f.func
        else:
            args: tuple[Any, ...] = ()
            kwargs: dict[str, Any] = {}

        if (instance := getattr(f, "__self__", None)) is not None:
            if hasattr(f, "__func__"):
                # Python bound method
                self._context = _WeakSlotPointer(weak_function=WeakMethod(f), args=args, kwargs=kwargs)
            else:
                # C-extension / PySide method
                self._context = _WeakSlotInfo(weak_instance=ref(instance), method=f.__name__, args=args, kwargs=kwargs)
        else:
            # normal Python function
            self._context = _StrongSlotInfo(function=f, args=args, kwargs=kwargs)

    def _get_function(self) -> F | None:
        match self._context:
            case _WeakSlotPointer(weak_function, args, kwargs):
                if f := weak_function():
                    return partial(f, *args, **kwargs)

            case _WeakSlotInfo(weak_instance, method, args, kwargs):
                if (obj := weak_instance()) and (f := getattr(obj, method, None)):
                    return partial(f, *args, **kwargs)

            case _StrongSlotInfo(f, args, kwargs):
                return partial(f, *args, **kwargs)

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
