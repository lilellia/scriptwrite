from pathlib import Path
import tomllib
from typing import get_args, Literal, TypeAlias

from scriptwrite.widgets.display import Color

ColorGroup: TypeAlias = Literal["reds", "oranges", "yellows", "greens", "blues", "purples", "magentas", "greys"]

# This is a big map of X11 colours, with CSS3 colours where they don't conflict with the X11 values.
with open(Path(__file__).parent / "color_names.toml", "rb") as f:
    NAMED_COLORS = tomllib.load(f)


def parse_color_input(value: str | list[int]) -> Color:
    match value:
        case str():
            # try to parse it as one of the above named colours
            key = value.strip().lower().replace(" ", "").replace("-", "")
            if key in NAMED_COLORS:
                hex = NAMED_COLORS[key]
                return Color.from_hex(hex)

            # try to parse it as a hex string
            if (color := Color.from_hex(value))._proxy.isValid():
                return color

        case [r, g, b] if isinstance(r, int) and isinstance(g, int) and isinstance(b, int):
            return Color.from_rgb(r, g, b)

    raise ValueError(f"Invalid color: {value}")


def color_groups() -> dict[ColorGroup, list[Color]]:
    result: dict[ColorGroup, list[Color]] = {}

    # basically set it up as a defaultdict(list) but force the correct ordering
    for group in get_args(ColorGroup):
        result[group] = []

    # partition the colors
    for code in set(NAMED_COLORS.values()):
        color = Color.from_hex(code)

        hue, saturation, _ = color.as_hsl()

        if saturation < 0.15:
            result["greys"].append(color)
            continue

        if 0 <= hue < 15:
            result["reds"].append(color)

        elif 15 <= hue < 45:
            result["oranges"].append(color)

        elif 45 <= hue < 80:
            result["yellows"].append(color)

        elif 80 <= hue < 150:
            result["greens"].append(color)

        elif 150 <= hue < 260:
            result["blues"].append(color)

        elif 260 <= hue < 285:
            result["purples"].append(color)

        elif 285 <= hue < 340:
            result["magentas"].append(color)

        else:
            result["reds"].append(color)

    # and sort the buckets
    for key in get_args(ColorGroup)[:-1]:

        def _keyfunc(c: Color) -> tuple[float, float, int]:
            h, s, light = c.as_hsl()
            return (light, s, h)

        result[key].sort(key=_keyfunc)

    result["greys"].sort(key=lambda c: c.as_hsl().lightness)

    return result


def get_color_name(color: Color) -> str:
    target = color.as_hex().lower()
    for key, code in NAMED_COLORS.items():
        if code.lower() == target:
            return key

    raise ValueError(f"no known name for color {color}")
