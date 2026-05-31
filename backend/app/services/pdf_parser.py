"""PDF text extraction with smart page filtering."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

LEGAL_KEYWORDS = [
    "terms and conditions", "general terms", "standard terms", "legal notice",
    "governing law", "dispute resolution", "indemnification", "liability clause",
    "force majeure", "confidentiality agreement"
]


def extract_pdf_text(filepath: str) -> str:
    """
    Extract text from PDF with smart page filtering.
    Always keeps page 1 and last page. Scores intermediate pages for data vs legal content.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(filepath)
        total_pages = len(reader.pages)

        if total_pages == 0:
            return ""

        selected_pages = []

        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""

            # Always include first and last page
            if i == 0 or i == total_pages - 1:
                selected_pages.append(text)
                continue

            # Score intermediate pages
            if _is_data_page(text):
                selected_pages.append(text)
            else:
                logger.debug(f"Skipping page {i+1} — appears to be legal/boilerplate content")

        return "\n\n---PAGE BREAK---\n\n".join(selected_pages)

    except Exception as e:
        logger.error(f"PDF extraction failed for {filepath}: {e}")
        return ""


def _is_data_page(text: str) -> bool:
    """Determine if a page contains order data vs legal boilerplate."""
    lower_text = text.lower()

    legal_score = sum(1 for kw in LEGAL_KEYWORDS if kw in lower_text)
    if legal_score >= 2:
        return False

    # Pages with numbers (quantities, prices) are likely data pages
    digit_count = sum(1 for c in text if c.isdigit())
    if digit_count > 20:
        return True

    return True  # Default: include the page