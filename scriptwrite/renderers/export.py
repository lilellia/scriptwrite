from pathlib import Path

from scriptwrite.config import ExportConfig
from scriptwrite.parser import Script
from scriptwrite.renderers.html import render_html

# from scriptwrite.renderers.latex import render_latex
from scriptwrite.renderers.odf import write_odt
from scriptwrite.renderers.scriptbin import render_scriptbin


def export(script: Script, path: Path, config: ExportConfig) -> None:
    match path.suffix:
        case ".html":
            content = render_html(script, config=config)
            path.write_text(content, encoding="utf-8")
        # case ".tex":
        #     content = render_latex(script, latex_template=Path(), config=config)
        #     path.write_text(content, encoding="utf-8")

        case ".md":
            content = render_scriptbin(script, config=config)
            path.write_text(content, encoding="utf-8")

        case ".odt":
            write_odt(script, path, config=config)
        case _:
            raise ValueError(f"Invalid suffix {path.suffix}")
