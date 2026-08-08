from dataclasses import asdict, dataclass, fields
import textwrap
import tomllib
from typing import Literal, Self, TypedDict

from scriptwrite.fs import APP_DIRS
from scriptwrite.log import logger


class ConfigDict(TypedDict):
    mode: Literal["light", "dark", "system"]
    theme: str
    font_size: int
    use_gtk_style: bool


@dataclass(slots=True)
class Config:
    theme: str = "breeze-dark"
    font_size: int = 12

    def write(self) -> None:
        path = APP_DIRS.config / "config.toml"

        config = textwrap.dedent(f"""\
        # Changes only take effect when scriptwrite is loaded

        # breeze-light | breeze-dark | dracula | catpuccin-latte | catpuccin-mocha | ayu-dark (default = "breeze-dark")
        # Use theme = "none" to query the system.
        theme = "{self.theme}"

        # font size (pt) used for the editor and preview windows (default=12)
        font_size = {self.font_size}
        """)

        with open(path, "w", encoding="utf-8") as f:
            f.write(config)

    @classmethod
    def load(cls) -> Self:
        path = APP_DIRS.config / "config.toml"

        if not path.exists():
            # just use defaults
            logger.warning(f"config file {path} not found")
            return cls()

        with open(path, "rb") as f:
            kwargs = tomllib.load(f)

        # try not to explode if the user puts bad keys in the config file
        valid_keys = set(f.name for f in fields(cls))
        found_keys = set(kwargs.keys())

        if unknown := set.difference(found_keys, valid_keys):
            logger.warning(f"Found unknown keys in config file (will be ignored): {unknown}")

        kwargs = {k: v for k, v in kwargs.items() if k in valid_keys}

        return cls(**kwargs)

    def as_dict(self) -> ConfigDict:
        return ConfigDict(**asdict(self))
