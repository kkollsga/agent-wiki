"""Word (.docx) to markdown conversion — placeholder."""

from pathlib import Path


def convert_docx(docx_path: Path, output_path: Path, **kwargs) -> Path:
    """Convert a Word document to markdown.

    Not yet implemented. Planned dependency: python-docx.
    """
    raise NotImplementedError(
        "Word (.docx) to markdown conversion is not yet implemented. "
        "Workaround: pandoc input.docx -o output.md"
    )
