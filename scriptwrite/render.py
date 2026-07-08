from collections.abc import Callable
from enum import auto, Enum

from scriptwrite.parser import Script
from scriptwrite.renderers.html import render_html


class RenderSchema(Enum):
    HTML = auto()


RENDERERS: dict[RenderSchema, Callable[[Script], str]] = {RenderSchema.HTML: render_html}


def write(script: Script, *, schema: RenderSchema) -> str:
    return RENDERERS[schema](script)
