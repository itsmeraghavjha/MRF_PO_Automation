"""Excel/CSV text extraction for PO processing."""
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def extract_excel_text(filepath: str) -> str:
    """Convert Excel/CSV to a readable text representation for LLM extraction."""
    try:
        if filepath.lower().endswith(".csv"):
            df = pd.read_csv(filepath, nrows=500)
        elif filepath.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(filepath, nrows=500)
        else:
            return ""

        # Convert to string representation
        text_parts = []
        text_parts.append(f"File: {filepath}")
        text_parts.append(f"Columns: {', '.join(df.columns.astype(str))}")
        text_parts.append("")
        text_parts.append(df.to_string(index=False, max_rows=200))

        return "\n".join(text_parts)

    except Exception as e:
        logger.error(f"Excel extraction failed for {filepath}: {e}")
        return ""