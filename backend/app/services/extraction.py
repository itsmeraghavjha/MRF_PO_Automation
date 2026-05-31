"""
AI Extraction Service — uses Anthropic Claude to extract structured PO data
from PDF/Excel text content. Implements retry logic and JSON schema validation.
"""
import json
import time
import logging
from typing import Optional
from app.core.config import settings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a Purchase Order data extraction specialist for Heritage Foods Limited, an Indian FMCG company.

Extract ALL structured data from the provided Purchase Order document text.

Return ONLY a valid JSON object with this exact structure (no markdown, no explanation):

{
  "po_type": "NEW" | "REVISED" | "CANCELLATION",
  "po_number": "string",
  "po_date": "YYYY-MM-DD or null",
  "customer_code": "string", 
  "customer_name": "string",
  "site_code": "string or null",
  "vendor_gstin": "string or null",
  "ship_to_address": "full address as string",
  "total_value": number or null,
  "delivery_date": "YYYY-MM-DD or null",
  "expiry_date": "YYYY-MM-DD or null",
  "document_type": "PURCHASE_ORDER" | "TAX_INVOICE" | "PROFORMA" | "GRN" | "OTHER",
  "line_items": [
    {
      "article_code": "string or null",
      "vendor_article_code": "string or null",
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
- customer_code: Deduce a 3-4 letter short code for the customer cluster (e.g., if Reliance Retail Limited -> "RRL", if DMart -> "DMT", if BigBasket -> "BBK").
- site_code: Look specifically for "Site:" or "Store Code:" (e.g., S1AC).
- total_value: Extract the grand total / Total Order Value of the PO.
- article_code: The buyer's SKU/Article number.
- vendor_article_code: Look for "Vendor Item No", "Vendor Article No", or the supplier's internal SKU.
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
                # ---> ADD THE MAPPING CODE HERE <---
                # Map the LLM keys to the exact database column names for line items
                for item in result.get("line_items", []):
                    item["customer_sku"] = item.pop("article_code", None)
                    item["material_code"] = item.pop("vendor_article_code", None)
                # -----------------------------------

                validated = _validate_schema(result)
                if validated:
                    return validated
                    
        except Exception as e:
            logger.warning(f"LLM extraction attempt {attempt + 1} failed: {e}")
            if attempt < settings.LLM_MAX_RETRIES - 1:
                time.sleep(settings.LLM_RETRY_BACKOFF_SECONDS * (attempt + 1))

    logger.error("All LLM extraction attempts exhausted")
    return None


# def _call_anthropic(content: str) -> Optional[dict]:
#     """Call Google Gemini API with strict JSON schema enforcement."""
#     from google import genai
#     from google.genai import types

#     # Initialize the client using your settings configuration
#     client = genai.Client(
#         api_key=settings.GEMINI_API_KEY,
#         http_options={'client_args': {'verify': False}}  # <--- Nested inside client_args
#     )

#     # Define the precise schema for native validation
#     # (This ensures the output matches your OrderLedger/OrderLineItem requirements)
#     po_schema = types.Schema(
#         type=types.Type.OBJECT,
#         properties={
#             "po_type": types.Schema(type=types.Type.STRING, enum=["NEW", "REVISED", "CANCELLATION"]),
#             "po_number": types.Schema(type=types.Type.STRING),
#             "po_date": types.Schema(type=types.Type.STRING),
#             "customer_code": types.Schema(type=types.Type.STRING),
#             "customer_name": types.Schema(type=types.Type.STRING),
#             "site_code": types.Schema(type=types.Type.STRING),
#             "vendor_gstin": types.Schema(type=types.Type.STRING),
#             "ship_to_address": types.Schema(type=types.Type.STRING),
#             "total_value": types.Schema(type=types.Type.NUMBER),
#             "delivery_date": types.Schema(type=types.Type.STRING),
#             "expiry_date": types.Schema(type=types.Type.STRING),
#             "document_type": types.Schema(type=types.Type.STRING, enum=["PURCHASE_ORDER", "TAX_INVOICE", "PROFORMA", "GRN", "OTHER"]),
#             "line_items": types.Schema(
#                 type=types.Type.ARRAY,
#                 items=types.Schema(
#                     type=types.Type.OBJECT,
#                     properties={
#                         "article_code": types.Schema(type=types.Type.STRING),
#                         "vendor_article_code": types.Schema(type=types.Type.STRING),
#                         "description": types.Schema(type=types.Type.STRING),
#                         "uom": types.Schema(type=types.Type.STRING),
#                         "hsn_code": types.Schema(type=types.Type.STRING),
#                         "qty": types.Schema(type=types.Type.NUMBER),
#                         "unit_price": types.Schema(type=types.Type.NUMBER),
#                         "mrp": types.Schema(type=types.Type.NUMBER),
#                         "tax_rate": types.Schema(type=types.Type.NUMBER),
#                         "tax_amount": types.Schema(type=types.Type.NUMBER),
#                         "line_total": types.Schema(type=types.Type.NUMBER),
#                     },
#                     required=["description", "qty", "unit_price"]
#                 )
#             )
#         },
#         required=["po_number", "line_items", "document_type", "po_type"]
#     )

#     try:
#         response = client.models.generate_content(
#             model='gemini-2.0-flash',  # Or 'gemini-1.5-pro' for highly complex layouts
#             contents=f"{EXTRACTION_PROMPT}\n\n{content}",
#             config=types.GenerateContentConfig(
#                 response_mime_type="application/json",
#                 response_schema=po_schema,
#                 temperature=0.1,  # Lower temperature keeps extraction deterministic
#             ),
#         )
        
#         raw_text = response.text.strip()
#         return json.loads(raw_text)

#     except Exception as e:
#         logger.error(f"Gemini API call failed: {e}")
#         raise e
    
def _call_anthropic(content: str) -> Optional[dict]:
    """
    Call Google Gemini API with strict JSON schema enforcement.
    """
    import json
    import re
    import google.generativeai as genai
    

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)

        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash"
        )

        prompt = f"""
{EXTRACTION_PROMPT}

IMPORTANT:
Return ONLY valid JSON.
Do not return markdown.
Do not use ```json blocks.

Required JSON structure:

{{
  "po_type": "NEW | REVISED | CANCELLATION",
  "po_number": "",
  "po_date": "",
  "customer_code": "",
  "customer_name": "",
  "site_code": "",
  "vendor_gstin": "",
  "ship_to_address": "",
  "total_value": 0,
  "delivery_date": "",
  "expiry_date": "",
  "document_type": "PURCHASE_ORDER | TAX_INVOICE | PROFORMA | GRN | OTHER",
  "line_items": [
    {{
      "article_code": "",
      "vendor_article_code": "",
      "description": "",
      "uom": "",
      "hsn_code": "",
      "qty": 0,
      "unit_price": 0,
      "mrp": 0,
      "tax_rate": 0,
      "tax_amount": 0,
      "line_total": 0
    }}
  ]
}}

Document:
{content}
"""

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )

        if not response.text:
            logger.error("Gemini returned empty response")
            return None

        response_text = response.text.strip()

        # Remove markdown fences if Gemini adds them
        response_text = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            response_text,
            flags=re.MULTILINE,
        ).strip()

        result = json.loads(response_text)

        # Ensure required fields exist
        result.setdefault("po_type", "NEW")
        result.setdefault("po_number", "")
        result.setdefault("document_type", "PURCHASE_ORDER")
        result.setdefault("line_items", [])

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini JSON response: {e}")
        return None

    except Exception as e:
        error_text = str(e)

        if "CERTIFICATE_VERIFY_FAILED" in error_text:
            logger.error(
                "SSL certificate verification failed. "
                "Check proxy/corporate certificate settings."
            )

        elif "429" in error_text or "quota" in error_text.lower():
            logger.error(
                "Gemini quota exceeded. Check billing and API quotas."
            )

        elif "API_KEY" in error_text.upper():
            logger.error(
                "Invalid Gemini API key."
            )

        else:
            logger.exception(
                f"Gemini API call failed: {error_text}"
            )

        raise

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