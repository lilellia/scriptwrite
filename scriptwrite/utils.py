from collections.abc import Mapping
from dataclasses import fields
from typing import TypeVar, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from _typeshed import DataclassInstance
    C = TypeVar("C", bound=DataclassInstance)


def load_dataclass(cls: type[C], data: Mapping[str, Any]) -> C:
    kwargs: dict[str, Any] = {}

    for f in fields(cls):
        if f.name not in data:
            continue

        converter = f.metadata.get("converter", lambda x: x)
        kwargs[f.name] = converter(data[f.name])

    return cls(**kwargs)
