from dataclasses import dataclass, field, fields
import textwrap
import tomllib
from typing import Self, TypedDict

from scriptwrite.fs import APP_DIRS
from scriptwrite.log import logger


class UIConfigDict(TypedDict):
    font_size: int
    font_family: str


class EditorConfigDict(TypedDict):
    font_size: int
    font_family: str


class ConfigDict(TypedDict):
    theme: str
    reload_last_file: bool
    ui: UIConfigDict
    editor: EditorConfigDict


@dataclass(slots=True)
class UIConfig:
    font_size: int = 12
    font_family: str = "[sans-serif]"

    def as_dict(self) -> UIConfigDict:
        return UIConfigDict(font_size=self.font_size, font_family=self.font_family)


@dataclass(slots=True)
class EditorConfig:
    font_size: int = 12
    font_family: str = "[serif]"

    def as_dict(self) -> EditorConfigDict:
        return EditorConfigDict(font_size=self.font_size, font_family=self.font_family)


@dataclass(slots=True)
class Config:
    theme: str = "breeze-dark"
    reload_last_file: bool = True
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

        # On empty launch, whether the application should load the previously opened file (true)
        # or should load an empty file (false).
        # (default=true)
        reload_last_file = {str(self.reload_last_file).lower()}

        [ui]
        # font size (pt) used for the menu bar and status bar (default=12)
        font_size = {self.ui.font_size}

        # font family used for the menu bar and status bar, e.g., "Arial" (default = "[sans-serif]")
        # In addition to providing a concrete font name, the following classes can be used to query the system:
        # [sans-serif] | [serif] | [monospace] | [any] | [system] | [typewriter] | [decorative] | [cursive] | [fantasy]
        font_family = "{self.ui.font_family}"

        [editor]
        # font size (pt) used for the editor and preview windows (default=12)
        font_size = {self.editor.font_size}

        # font family used for the editor and preview windows, e.g., "Times New Roman" (default = "[serif]")
        # In addition to providing a concrete font name, the following classes can be used to query the system:
        # [sans-serif] | [serif] | [monospace] | [any] | [system] | [typewriter] | [decorative] | [cursive] | [fantasy]
        font_family = "{self.editor.font_family}"
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
        return ConfigDict(
            theme=self.theme, reload_last_file=self.reload_last_file, ui=self.ui.as_dict(), editor=self.editor.as_dict()
        )
