"""
PDF Text Extraction — Heritage Foods PO Automation
===================================================
Smart page filtering: keeps data-rich pages, drops legal boilerplate.

The original _is_data_page() always returned True, meaning ALL pages were
sent to the LLM regardless of content. For Reliance POs (11-12 pages with
extensive T&C sections) this wastes tokens and degrades extraction accuracy.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Legal/boilerplate keyword patterns — pages with 2+ matches are dropped
LEGAL_KEYWORDS = [
    "terms and conditions",
    "general terms",
    "standard terms",
    "legal notice",
    "governing law",
    "dispute resolution",
    "indemnification",
    "liability clause",
    "force majeure",
    "confidentiality agreement",
    "arbitration",
    "jurisdiction",
    "intellectual property",
    "without prejudice",
    "notwithstanding",
    "warranty disclaimer",
]

# Data-bearing keywords — any match strongly suggests this is a data page
DATA_KEYWORDS = [
    "material",
    "article",
    "qty",
    "quantity",
    "price",
    "amount",
    "uom",
    "hsn",
    "ean",
    "barcode",
    "delivery date",
    "ship to",
    "gstin",
    "tax",
    "total",
]

# Maximum pages to send to LLM (cost + latency guard)
MAX_PAGES = 15


def extract_pdf_text(filepath: str) -> str:
    """
    Extract text from PDF with smart page filtering.

    Strategy:
    - Always include page 1 (header / PO details) and last page (totals / signatures).
    - For intermediate pages: score as data vs legal content.
    - Cap at MAX_PAGES to prevent runaway token usage.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(filepath)
        total_pages = len(reader.pages)

        if total_pages == 0:
            return ""

        selected_pages = []
        skipped_count = 0

        for i, page in enumerate(reader.pages):
            if len(selected_pages) >= MAX_PAGES:
                logger.info(
                    f"PDF {filepath}: hit {MAX_PAGES} page limit at page {i+1}/{total_pages}"
                )
                break

            text = page.extract_text() or ""

            # Always include first and last page
            if i == 0 or i == total_pages - 1:
                selected_pages.append(text)
                continue

            if _is_data_page(text):
                selected_pages.append(text)
            else:
                skipped_count += 1
                logger.debug(f"PDF {filepath}: skipping page {i+1} (legal/boilerplate)")

        if skipped_count:
            logger.info(
                f"PDF {filepath}: {len(selected_pages)} data pages, "
                f"{skipped_count} boilerplate pages skipped"
            )

        return "\n\n---PAGE BREAK---\n\n".join(selected_pages)

    except Exception as e:
        logger.error(f"PDF extraction failed for {filepath}: {e}")
        return ""


def _is_data_page(text: str) -> bool:
    """
    Determine if a page contains PO data vs legal boilerplate.

    Decision logic:
      1. If 2+ legal keywords found → drop (boilerplate)
      2. If any data keyword found  → keep (has PO data)
      3. If 20+ digit characters    → keep (has numbers = likely data)
      4. Default                    → drop (when in doubt, exclude)

    The original code defaulted to True (include everything).
    We default to False (exclude when uncertain) to protect LLM token budget.
    """
    lower_text = text.lower()

    # Strong legal signal — drop the page
    legal_score = sum(1 for kw in LEGAL_KEYWORDS if kw in lower_text)
    if legal_score >= 2:
        return False

    # Strong data signal — keep the page
    data_score = sum(1 for kw in DATA_KEYWORDS if kw in lower_text)
    if data_score >= 1:
        return True

    # Numeric density — tables of quantities/prices have lots of digits
    digit_count = sum(1 for c in text if c.isdigit())
    if digit_count > 20:
        return True

    # Default: exclude — when we can't tell, it's safer to drop
    # (a real data page will almost always have at least one data keyword)
    return False