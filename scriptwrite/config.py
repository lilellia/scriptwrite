from dataclasses import dataclass
from typing import Literal, Self

from ruamel.yaml import YAML

from scriptwrite.fs import APP_DIRS
from scriptwrite.log import logger


@dataclass(slots=True)
class Config:
    mode: Literal["light", "dark", "system"] = "system"
    font_size: int = 12

    @classmethod
    def load(cls) -> Self:
        path = APP_DIRS.config / "config.yaml"

        if not path.exists():
            # just use defaults
            logger.warning(f"config file {path} not found")
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            kwargs = YAML(typ="safe").load(f)
            return cls(**kwargs)
