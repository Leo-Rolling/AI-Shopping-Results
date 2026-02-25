"""File-based export (CSV, Excel) for SP-API data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

# Default output directory
_OUTPUT_DIR = Path("output")


class FileExporter:
    """Export DataFrames to CSV or Excel files."""

    def __init__(self, output_dir: Path | str = _OUTPUT_DIR) -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def export_dataframe(
        self,
        df: pd.DataFrame,
        name: str,
        output_format: str = "csv",
    ) -> Path:
        """Export a DataFrame to a file.

        Args:
            df: Data to export.
            name: Base filename (without extension).
            output_format: "csv" or "excel".

        Returns:
            Path to the generated file.
        """
        if output_format == "excel":
            return self._export_excel(df, name)
        return self._export_csv(df, name)

    def _export_csv(self, df: pd.DataFrame, name: str) -> Path:
        """Export DataFrame to CSV."""
        path = self._output_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        logger.info("Exported CSV", path=str(path), rows=len(df))
        return path

    def _export_excel(self, df: pd.DataFrame, name: str) -> Path:
        """Export DataFrame to Excel."""
        path = self._output_dir / f"{name}.xlsx"
        df.to_excel(path, index=False, engine="openpyxl")
        logger.info("Exported Excel", path=str(path), rows=len(df))
        return path

    def export_multiple(
        self,
        dataframes: dict[str, pd.DataFrame],
        name: str,
        output_format: str = "csv",
    ) -> list[Path]:
        """Export multiple DataFrames.

        For CSV: creates one file per DataFrame.
        For Excel: creates one file with multiple sheets.

        Args:
            dataframes: Dict of sheet_name -> DataFrame.
            name: Base filename.
            output_format: "csv" or "excel".

        Returns:
            List of generated file paths.
        """
        if output_format == "excel":
            path = self._output_dir / f"{name}.xlsx"
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                for sheet_name, df in dataframes.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            logger.info("Exported multi-sheet Excel", path=str(path), sheets=len(dataframes))
            return [path]

        # CSV: one file per DataFrame
        paths = []
        for sheet_name, df in dataframes.items():
            path = self._export_csv(df, f"{name}_{sheet_name}")
            paths.append(path)
        return paths
