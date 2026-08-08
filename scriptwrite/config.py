from dataclasses import asdict, dataclass, field, fields
import textwrap
import tomllib
from typing import Self, TypedDict

from scriptwrite.fs import APP_DIRS
from scriptwrite.log import logger


class ConfigDict(TypedDict):
    theme: str
    font_size: int
    use_gtk_style: bool


@dataclass(slots=True)
class UIConfig:
    font_size: int = 12
    font_family: str = "[sans-serif]"


@dataclass(slots=True)
class EditorConfig:
    font_size: int = 12
    font_family: str = "[serif]"


@dataclass(slots=True)
class Config:
    theme: str = "breeze-dark"
    ui: UIConfig = field(default_factory=UIConfig)
    editor: EditorConfig = field(default_factory=EditorConfig)

    def write(self) -> None:
        path = APP_DIRS.config / "config.toml"

        config = textwrap.dedent(f"""\
        # Changes only take effect when scriptwrite is loaded

        # The color theme for the application (default = "breeze-dark")
        # light themes: alucard | ayu-light | breeze-light | catpuccin-latte | github-light
        # dark themes: ayu-dark | ayu-mirage | breeze-dark | catpuccin-mocha | dracula | github-dark
        #
        # You can also use any theme defined in {APP_DIRS.config / "themes"}.
        theme = "{self.theme}"

        [ui]
        # font size (pt) used for the menu bar and status bar (default=12)
        font_size = {self.ui.font_size}

        # font family used for the menu bar and status bar, e.g., "Arial" (default = "[sans-serif]")
        # In addition to providing a concrete font name, the following classes can be used to query the system:
        # [sans-serif] | [serif] | [monospace] | [any] | [system] | [typewriter] | [decorative] | [cursive] | [fantasy]
        font_family = "[sans-serif]"

        [editor]
        # font size (pt) used for the editor and preview windows (default=12)
        font_size = {self.editor.font_size}

        # font family used for the editor and preview windows, e.g., "Times New Roman" (default = "[serif]")
        # In addition to providing a concrete font name, the following classes can be used to query the system:
        # [sans-serif] | [serif] | [monospace] | [any] | [system] | [typewriter] | [decorative] | [cursive] | [fantasy]
        font_family = "[serif]"
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

        kwargs["ui"] = UIConfig(**kwargs.get("ui", {}))
        kwargs["editor"] = EditorConfig(**kwargs.get("editor", {}))

        return cls(**kwargs)

    def as_dict(self) -> ConfigDict:
        return ConfigDict(**asdict(self))
