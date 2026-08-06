from dataclasses import asdict, dataclass, field, fields
import textwrap
import tomllib
from typing import Literal, Self, TypedDict

from scriptwrite.fs import APP_DIRS
from scriptwrite.log import logger
from scriptwrite.utils import load_dataclass
from scriptwrite.widgets.display import Color


class ConfigDict(TypedDict):
    mode: Literal["light", "dark", "system"]
    font_size: int
    use_gtk_style: bool
    highlight_color: Color


@dataclass(slots=True)
class Config:
    mode: Literal["light", "dark", "system"] = "system"
    font_size: int = 12
    use_gtk_style: bool = False
    highlight_color: Color = field(
        default_factory=lambda: Color.from_hex("#FFF3CD"), metadata=dict(converter=Color.from_hex)
    )

    def write(self) -> None:
        path = APP_DIRS.config / "config.toml"

        config = textwrap.dedent(f"""\
        # Changes only take effect when scriptwrite is loaded

        # light | dark | system  (default=system)
        mode = "{self.mode}"

        # font size (pt) used for the editor and preview windows (default=12)
        font_size = {self.font_size}

        # Whether the application should pull GTK styling (default=false)
        # This value is ignored on non-Linux systems.
        use_gtk_style = {str(self.use_gtk_style).lower()}

        # the color of the block highlight used to mark the scroll-sync paragraph (default = "$FFF3CD")
        highlight_color = "{self.highlight_color}"
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

        return load_dataclass(cls, kwargs)

    def as_dict(self) -> ConfigDict:
        return ConfigDict(**asdict(self))
