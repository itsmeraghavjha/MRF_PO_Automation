"""
AI Extraction Service — Heritage Foods PO Automation
=====================================================
Uses Google Gemini (or Anthropic Claude as fallback) to extract structured
PO data from PDF/Excel text.

Key design:
  - Customer profile is identified BEFORE extraction so customer-specific
    rules can be injected into the prompt (fewer hallucinations, better accuracy).
  - Returns a normalised dict with consistent field names regardless of which
    customer sent the PO.
  - All customer-specific column name quirks are handled HERE, not in validation.
"""
import json
import time
import logging
import re
from typing import Optional
from app.core.config import settings
from app.services.customer_profiles import (
    CustomerProfile,
    get_extraction_rules_for_prompt,
    VR01_EAN_ONLY,
)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# ── Base extraction prompt ─────────────────────────────────────────────────
BASE_EXTRACTION_PROMPT = """You are a Purchase Order data extraction specialist for Heritage Foods Limited, an Indian FMCG company.

Extract ALL structured data from the provided Purchase Order document text.

Return ONLY a valid JSON object with this exact structure (no markdown, no explanation, no ```json blocks):

{
  "po_type": "NEW" | "REVISED" | "CANCELLATION",
  "po_number": "string",
  "po_date": "YYYY-MM-DD or null",
  "customer_code": "string",
  "customer_name": "string",
  "customer_gstin": "string or null",
  "site_code": "string or null",
  "ship_to_address": "full address as string",
  "total_value": number or null,
  "delivery_date": "YYYY-MM-DD or null",
  "expiry_date": "YYYY-MM-DD or null",
  "document_type": "PURCHASE_ORDER" | "TAX_INVOICE" | "PROFORMA" | "GRN" | "OTHER",
  "line_items": [
    {
      "article_code": "string or null",
      "vendor_article_code": "string or null",
      "ean": "string or null",
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

GENERAL RULES:
- po_type: "REVISED" if subject/content has "revised", "amendment", "update". "CANCELLATION" if "cancel". Otherwise "NEW".
- customer_code: Deduce a short 3-6 letter code (e.g. Reliance Retail → "RRL", DMart → "DMT", Zepto → "ZEP").
- customer_gstin: The GSTIN of the company that sent this Purchase Order (the buyer). This is their GST registration number printed near their company name/address at the top of the PO. Do NOT extract Heritage Foods' GSTIN — Heritage is the supplier receiving this PO, not the buyer.
- site_code: Look for "Site:", "Store Code:", "DC Code:", "Vendor Location Code".
- ean: 13-digit barcode number (usually starts with 890 for Heritage products).
- article_code: The buyer's own SKU / Article number.
- vendor_article_code: The supplier's (Heritage's) article code on the PO.
- document_type: If Tax Invoice, Proforma Invoice, GRN, Payment Advice — set accordingly.
- All monetary values in INR numbers only (no ₹ symbol).
- Dates must be YYYY-MM-DD. Indian format is DD/MM/YYYY — parse accordingly.
- Extract ALL line items — do not truncate or summarise.
- If a field is not present, use null.
"""


def extract_po_data(
    text_content: str,
    subject: str = "",
    profile: Optional[CustomerProfile] = None,
) -> Optional[dict]:
    """
    Extract structured PO data from document text using AI.

    Args:
        text_content: Raw text extracted from the PDF/Excel attachment.
        subject:      Email subject line (provides context about PO type).
        profile:      Customer profile (if already identified). When provided,
                      customer-specific extraction rules are injected into the prompt
                      for much higher accuracy.

    Returns:
        Normalised dict ready for ingestion, or None if extraction fails.
    """
    # Build the prompt
    customer_rules = ""
    if profile:
        customer_rules = get_extraction_rules_for_prompt(profile)

    combined_input = f"Email Subject: {subject}\n\nDocument Content:\n{text_content}"

    for attempt in range(settings.LLM_MAX_RETRIES):
        try:
            result = _call_llm(combined_input, customer_rules=customer_rules)

            if result:
                # Normalise field names from LLM output to DB column names
                _normalise_line_items(result, profile)

                validated = _validate_schema(result)
                if validated:
                    return validated

        except Exception as e:
            logger.warning(f"LLM extraction attempt {attempt + 1} failed: {e}")
            if attempt < settings.LLM_MAX_RETRIES - 1:
                time.sleep(settings.LLM_RETRY_BACKOFF_SECONDS * (attempt + 1))

    logger.error("All LLM extraction attempts exhausted")
    return None


def _normalise_line_items(result: dict, profile: Optional[CustomerProfile]) -> None:
    """
    Map LLM field names to DB column names, applying customer-specific logic.

    This is where all the per-customer field mapping quirks are resolved
    so the rest of the pipeline can work with consistent field names.
    """
    for item in result.get("line_items", []):
        # ── EAN: collect from multiple possible source fields ────────────
        ean_raw = item.pop("ean", None)
        article_code = item.pop("article_code", None)
        vendor_article_code = item.pop("vendor_article_code", None)

        # For Reliance: vendor_article_code IS the EAN (not a material code)
        if profile and profile.vendor_article_is_ean:
            ean = vendor_article_code or ean_raw
            customer_sku = article_code        # Article No. → customer_sku
            material_code = None               # NEVER map Reliance's article no. as HFL code
        else:
            ean = ean_raw
            customer_sku = article_code
            material_code = vendor_article_code

        # Validate EAN format (13-digit, starts with 890 for Heritage)
        if ean:
            ean = str(ean).strip().replace(" ", "")
            if not re.match(r"^\d{13}$", ean):
                logger.debug(f"Discarding malformed EAN: {ean!r}")
                ean = None

        # For DMart: no material code exists
        if profile and profile.vr01_strategy == VR01_EAN_ONLY:
            material_code = None

        item["ean"] = ean
        item["customer_sku"] = customer_sku
        item["material_code"] = material_code


def _call_llm(content: str, customer_rules: str = "") -> Optional[dict]:
    """Call Gemini API with the full prompt including customer-specific rules."""
    import google.generativeai as genai

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name="gemini-2.5-flash")

        # Inject customer-specific rules between base prompt and document
        customer_section = ""
        if customer_rules.strip():
            customer_section = f"\n\nCUSTOMER-SPECIFIC EXTRACTION RULES (OVERRIDE GENERAL RULES):\n{customer_rules}\n"

        prompt = (
            BASE_EXTRACTION_PROMPT
            + customer_section
            + "\n\nIMPORTANT: Return ONLY valid JSON. No markdown. No ```json blocks.\n\n"
            + f"Document:\n{content}"
        )

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )

        if not response.text:
            logger.error("LLM returned empty response")
            return None

        response_text = response.text.strip()
        # Strip markdown fences if model ignores the instruction
        response_text = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", response_text, flags=re.MULTILINE
        ).strip()

        result = json.loads(response_text)
        result.pop("vendor_gstin", None)

        # Ensure required fields have safe defaults
        result.setdefault("po_type", "NEW")
        result.setdefault("po_number", "")
        result.setdefault("document_type", "PURCHASE_ORDER")
        result.setdefault("line_items", [])

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        return None

    except Exception as e:
        error_text = str(e)
        if "CERTIFICATE_VERIFY_FAILED" in error_text:
            logger.error("SSL certificate verification failed. Check proxy/corporate certificate settings.")
        elif "429" in error_text or "quota" in error_text.lower():
            logger.error("Gemini quota exceeded. Check billing and API quotas.")
        elif "API_KEY" in error_text.upper():
            logger.error("Invalid Gemini API key.")
        else:
            logger.exception(f"LLM API call failed: {error_text}")
        raise


def _validate_schema(data: dict) -> Optional[dict]:
    """Validate extracted data has the minimum required structure."""
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

    for i, item in enumerate(data["line_items"]):
        if not item.get("description"):
            logger.debug(f"Line item {i} missing description — will rely on codes for matching")
        if item.get("qty") is None:
            logger.warning(f"Line item {i} missing qty")

    return data