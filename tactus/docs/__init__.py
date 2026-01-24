"""
Tactus Documentation Generator.

Extract documentation from .tac files and generate HTML output.
"""

from pathlib import Path
from tactus.docs.extractor import DirectoryExtractor
from tactus.docs.html_renderer import HTMLRenderer


def generate_docs(input_path: Path, output_path: Path):
    """
    Generate HTML documentation from Tactus .tac files.

    Args:
        input_path: Path to directory containing .tac files
        output_path: Path where HTML files will be written
    """
    # Extract documentation
    extractor = DirectoryExtractor(input_path)
    tree = extractor.extract_all()

    print(f"Found {len(tree.modules)} module(s) to document")

    # Render HTML
    renderer = HTMLRenderer()
    renderer.render_all(tree, output_path)

    print(f"✓ Documentation generated at {output_path}/index.html")


__all__ = ["generate_docs", "DirectoryExtractor", "HTMLRenderer"]
