from dataclasses import dataclass, fields
import tomllib
from typing import Literal, Self

from scriptwrite.fs import APP_DIRS
from scriptwrite.log import logger


@dataclass(slots=True)
class Config:
    mode: Literal["light", "dark", "system"] = "system"
    font_size: int = 12

    @classmethod
    def load(cls) -> Self:
        path = APP_DIRS.config / "config.toml"

        if not path.exists():
            # just use defaults
            logger.warning(f"config file {path} not found")
            return cls()

        with open(path, "rb") as f:
            # ruamel returns None instead of an empty dict when the file is empty for... some reason
            kwargs = tomllib.load(f)

        # try not to explode if the user puts bad keys in the config file
        valid_keys = set(f.name for f in fields(cls))
        found_keys = set(kwargs.keys())

        if unknown := set.difference(found_keys, valid_keys):
            logger.warning(f"Found unknown keys in config file (will be ignored): {unknown}")

        kwargs = {k: v for k, v in kwargs.items() if k in valid_keys}

        return cls(**kwargs)
