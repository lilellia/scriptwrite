from pathlib import Path

from scriptwrite.config import ExportConfig
from scriptwrite.parser import Script, parse_text
from scriptwrite.renderers.fountain import render_fountain
from scriptwrite.renderers.html import render_html

# from scriptwrite.renderers.latex import render_latex
from scriptwrite.log import logger
from scriptwrite.renderers.odf import write_odt
from scriptwrite.renderers.scriptbin import render_scriptbin


def export_from_path(source: Path, target: Path, config: ExportConfig) -> None:
    with logger.stopwatch(f"Exporting {source} -> {target}"):
        script = parse_text(source.read_text())
        export(script, target, config)


def export(script: Script, path: Path, config: ExportConfig) -> None:
    match path.suffix:
        case ".html":
            export_format = "html"
            content = render_html(script, config=config)
            path.write_text(content, encoding="utf-8")
        # case ".tex":
        #     content = render_latex(script, latex_template=Path(), config=config)
        #     path.write_text(content, encoding="utf-8")

        case ".md":
            export_format = "scriptbin"
            content = render_scriptbin(script, config=config)
            path.write_text(content, encoding="utf-8")

        case ".odt":
            export_format = "odt"
            write_odt(script, path, config=config)

        case ".fountain":
            export_format = "fountain"
            content = render_fountain(script, config=config)
            path.write_text(content, encoding="utf-8")

        case _:
            raise ValueError(f"Invalid suffix {path.suffix}")

    logger.info("Exported script", target=path, format=export_format)
