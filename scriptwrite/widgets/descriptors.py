from collections.abc import Mapping
from functools import reduce
from typing import Any, Generic, overload, Self, TypeVar

from PySide6.QtCore import QObject

E = TypeVar("E")
K = TypeVar("K", bound=str)
T = TypeVar("T")
Q = TypeVar("Q", bound=QObject)


def default_set_name(get_name: str) -> str:
    return f"set{get_name[0].upper()}{get_name[1:]}"


def deep_getattr(obj: Any, dotted_name: str) -> Any:
    components = dotted_name.split(".")
    return reduce(lambda acc, attr: getattr(acc, attr), components, initial=obj)


class QtProperty(Generic[T]):
    def __init__(self, getter: str, setter: str | None = None) -> None:
        self._get_name = getter
        self._set_name = setter or default_set_name(getter)

    @overload
    def __get__(self, instance: None, owner: type[Q], /) -> Self: ...

    @overload
    def __get__(self, instance: Q, owner: type[Q], /) -> T: ...

    def __get__(self, instance: Q | None, owner: type[Q], /) -> Self | T:
        if instance is None:
            return self

        get = deep_getattr(instance, self._get_name)
        return get()

    def __set__(self, instance: QObject | None, value: T, /) -> None:
        if instance is None:
            return

        set = deep_getattr(instance, self._set_name)
        set(value)


class QtEnum(Generic[K]):
    def __init__(self, getter: str, key_to_enum: Mapping[K, E], setter: str | None = None) -> None:
        self._key_to_enum = key_to_enum
        self._enum_to_key = {v: k for k, v in key_to_enum.items()}
        self._get_name = getter
        self._set_name = setter or default_set_name(getter)

        if len(self._key_to_enum) != len(self._enum_to_key):
            raise ValueError(f"Invalid mapping: {key_to_enum}")

    @overload
    def __get__(self, instance: None, owner: type[Q], /) -> Self: ...

    @overload
    def __get__(self, instance: Q, owner: type[Q], /) -> K: ...

    def __get__(self, instance: Q | None, owner: type[Q], /) -> Self | K:
        if instance is None:
            return self

        get = deep_getattr(instance, self._get_name)
        e = get()
        return self._enum_to_key[e]

    def __set__(self, instance: QObject | None, value: K, /) -> None:
        if instance is None:
            return

        set = deep_getattr(instance, self._set_name)
        e = self._key_to_enum[value]
        set(e)
