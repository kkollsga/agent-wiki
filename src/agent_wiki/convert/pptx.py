"""PowerPoint (.pptx) to markdown conversion — placeholder."""

from pathlib import Path


def convert_pptx(pptx_path: Path, output_path: Path, **kwargs) -> Path:
    """Convert a PowerPoint presentation to markdown.

    Not yet implemented. Planned dependency: python-pptx.
    """
    raise NotImplementedError(
        "PowerPoint (.pptx) to markdown conversion is not yet implemented. "
        "Workaround: export slides as images, then reference in markdown."
    )
