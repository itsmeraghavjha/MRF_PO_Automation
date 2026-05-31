"""
AI Extraction Service — uses Anthropic Claude to extract structured PO data
from PDF/Excel text content. Implements retry logic and JSON schema validation.
"""
import json
import time
import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a Purchase Order data extraction specialist for Heritage Foods Limited, an Indian FMCG company.

Extract ALL structured data from the provided Purchase Order document text.

Return ONLY a valid JSON object with this exact structure (no markdown, no explanation):

{
  "po_type": "NEW" | "REVISED" | "CANCELLATION",
  "po_number": "string",
  "po_date": "YYYY-MM-DD or null",
  "customer_name": "string",
  "vendor_gstin": "string or null",
  "ship_to_address": "full address as string",
  "delivery_date": "YYYY-MM-DD or null",
  "expiry_date": "YYYY-MM-DD or null",
  "document_type": "PURCHASE_ORDER" | "TAX_INVOICE" | "PROFORMA" | "GRN" | "OTHER",
  "line_items": [
    {
      "article_code": "string or null",
      "description": "string",
      "uom": "string",
      "hsn_code": "string or null",
      "qty": number,
      "unit_price": number,
      "mrp": number or null,
      "tax_rate": number or null,
      "tax_amount": number or null,
      "line_total": number or null
    }
  ]
}

Rules:
- po_type: If subject/content mentions "revised", "amendment", "update" → REVISED. If "cancel" → CANCELLATION. Otherwise → NEW.
- document_type: If this is a Tax Invoice, Proforma Invoice, GRN, or Payment Advice — set accordingly. Only process as PURCHASE_ORDER if it truly is one.
- All monetary values in INR (numbers only, no currency symbols).
- Dates must be YYYY-MM-DD format. If date format is ambiguous (e.g. 01/05/2025), use context to determine DD/MM/YYYY (Indian standard).
- If a field is not present in the document, use null.
- Extract ALL line items — do not truncate.
- vendor_gstin: Look for "GSTIN", "GST No", "Tax ID" near Heritage Foods' details."""


def extract_po_data(text_content: str, subject: str = "") -> Optional[dict]:
    """
    Extract structured PO data from document text using Claude.
    Implements retry logic with exponential backoff.
    """
    combined_input = f"Email Subject: {subject}\n\nDocument Content:\n{text_content}"

    for attempt in range(settings.LLM_MAX_RETRIES):
        try:
            result = _call_anthropic(combined_input)
            if result:
                validated = _validate_schema(result)
                if validated:
                    return validated
        except Exception as e:
            logger.warning(f"LLM extraction attempt {attempt + 1} failed: {e}")
            if attempt < settings.LLM_MAX_RETRIES - 1:
                time.sleep(settings.LLM_RETRY_BACKOFF_SECONDS * (attempt + 1))

    logger.error("All LLM extraction attempts exhausted")
    return None


def _call_anthropic(content: str) -> Optional[dict]:
    """Call Anthropic Claude API."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": f"{EXTRACTION_PROMPT}\n\n{content}"
            }
        ]
    )

    raw_text = message.content[0].text.strip()

    # Strip markdown fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    return json.loads(raw_text)


def _validate_schema(data: dict) -> Optional[dict]:
    """Validate extracted data against expected schema."""
    required_fields = ["po_number", "line_items", "document_type", "po_type"]

    for field in required_fields:
        if field not in data:
            logger.warning(f"Extraction missing required field: {field}")
            return None

    if not isinstance(data.get("line_items"), list):
        logger.warning("line_items is not a list")
        return None

    if len(data["line_items"]) == 0:
        logger.warning("No line items extracted")
        return None

    # Validate each line item has at minimum description and qty
    for i, item in enumerate(data["line_items"]):
        if not item.get("description"):
            logger.warning(f"Line item {i} missing description")
        if item.get("qty") is None:
            logger.warning(f"Line item {i} missing qty")

    return data