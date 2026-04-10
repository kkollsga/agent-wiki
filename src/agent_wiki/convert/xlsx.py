"""Excel (.xlsx) to markdown conversion — placeholder."""

from pathlib import Path


def convert_xlsx(xlsx_path: Path, output_path: Path, **kwargs) -> Path:
    """Convert an Excel spreadsheet to markdown tables.

    Not yet implemented. Planned dependency: openpyxl.
    """
    raise NotImplementedError(
        "Excel (.xlsx) to markdown conversion is not yet implemented. "
        "Workaround: export as CSV, then format as markdown table."
    )
