"""
Render Tactus documentation as HTML.

Uses Jinja2 templates with clean, minimal styling.
"""

from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
import markdown
from tactus.docs.models import DocumentationTree, ModuleDoc


class HTMLRenderer:
    """Render documentation tree as HTML files."""

    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize renderer with templates.

        Args:
            template_dir: Path to Jinja2 templates. If None, uses built-in templates.
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        # Add custom filters
        self.env.filters["markdown"] = self._markdown_filter

    def _markdown_filter(self, text: str) -> str:
        """Convert markdown to HTML."""
        return markdown.markdown(
            text,
            extensions=["extra", "codehilite", "fenced_code"],
        )

    def render_module(self, module: ModuleDoc) -> str:
        """Render a single module's documentation."""
        template = self.env.get_template("module.html")
        return template.render(module=module)

    def render_index(self, tree: DocumentationTree) -> str:
        """Render the index page listing all modules."""
        template = self.env.get_template("index.html")
        return template.render(tree=tree)

    def render_all(self, tree: DocumentationTree, output_dir: Path):
        """
        Render all documentation to HTML files.

        Creates:
        - index.html (list of all modules)
        - <module-name>.html for each module
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Render index
        index_html = self.render_index(tree)
        (output_dir / "index.html").write_text(index_html)

        # Render each module
        for module in tree.modules:
            module_html = self.render_module(module)
            filename = f"{module.name}.html"
            (output_dir / filename).write_text(module_html)

        print(f"✓ Generated {len(tree.modules) + 1} HTML files in {output_dir}")
