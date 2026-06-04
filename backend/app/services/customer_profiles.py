"""
Customer Profiles Registry — Heritage Foods PO Automation
==========================================================
Single source of truth for all customer-specific PO processing behavior.

ARCHITECTURE NOTES (for scaling to 100+ customers):
----------------------------------------------------
Phase 1: Dict-based registry (fast, zero DB overhead, version-controlled)
Phase 2: Migrate to DB-backed CustomerProfileConfig table when > 20 customers
         or when ops staff need UI to manage profiles without code deploy.

Each profile defines:
  - Detection signals  : how to identify the customer from a PO
  - Extraction hints   : which fields map to which PO columns
  - VR-01 strategy     : product lookup order (material_code / ean / customer_sku / description)
  - VR-02 price field  : which extracted field to validate against NLC
  - VR-06 GSTIN flag   : whether missing GSTIN is a hard failure

Adding a new customer:
  1. Add an entry to CUSTOMER_PROFILES below.
  2. Add customer-specific extraction rules to CUSTOMER_EXTRACTION_RULES.
  3. Done — the pipeline picks it up automatically.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import logging
import re

logger = logging.getLogger(__name__)


# ── VR-01 strategy constants ───────────────────────────────────────────────
VR01_MATERIAL_CODE_PRIMARY    = "material_code_primary_ean_fallback"
VR01_EAN_PRIMARY              = "ean_primary_customer_sku_fallback"
VR01_EAN_ONLY                 = "ean_only"
VR01_CUSTOMER_SKU_PRIMARY     = "customer_sku_primary_description_fallback"
VR01_DESCRIPTION_ONLY         = "description_only"


# ── Profile dataclass ──────────────────────────────────────────────────────
@dataclass
class CustomerProfile:
    """
    Immutable profile for one customer cluster.
    All fields have safe defaults so adding a new customer requires
    only specifying the fields that differ from the generic baseline.
    """
    # Identity
    cluster: str                          # Short canonical code: ZEP, RRL, DMT…
    name: str                             # Human-readable display name

    # Detection signals (checked in priority order)
    name_keywords: list[str] = field(default_factory=list)   # Lowercase fragments
    gstin_list:    list[str] = field(default_factory=list)    # Known buyer GSTINs
    email_domains: list[str] = field(default_factory=list)    # Sender email domains
    po_title_keywords: list[str] = field(default_factory=list)# Keywords in PO title/subject

    # Extraction hints — tell the LLM which column names to use
    material_code_field:   Optional[str] = None   # HFL's own code column (if any)
    ean_field:             Optional[str] = None   # EAN / barcode column name
    vendor_article_is_ean: bool          = False  # Reliance: vendor_article_no = EAN
    price_field:           str           = "Base Cost"
    price_fallback_field:  Optional[str] = None
    discount_field:        Optional[str] = None
    site_code_pattern:     str           = "explicit_field"  # How site code appears on PO
    # Options: explicit_field | parenthetical | dc_number | gstin_based | store_name | address_only

    # Validation behaviour
    vr01_strategy:         str  = VR01_EAN_PRIMARY
    vr06_gstin_required:   bool = True

    # Misc
    document_type_warning: Optional[str] = None  # Flag unusual document formats
    notes:                 Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════
# CUSTOMER PROFILES REGISTRY
# ══════════════════════════════════════════════════════════════════════════
# Key = cluster code (must match CustomerMapping.cluster in DB)

CUSTOMER_PROFILES: dict[str, CustomerProfile] = {

    "ZEP": CustomerProfile(
        cluster="ZEP",
        name="Zepto",
        name_keywords=["zepto", "kiranakart"],
        gstin_list=["36AAICK4821A1ZW"],
        email_domains=["zepto.com", "kiranakart.com"],
        # Zepto puts HFL's own material code in "Material Code" column
        material_code_field="Material Code",
        ean_field="EAN No",
        vendor_article_is_ean=False,
        price_field="Base Cost",
        site_code_pattern="parenthetical",   # "(HYD096M)" at end of address
        vr01_strategy=VR01_MATERIAL_CODE_PRIMARY,
        vr06_gstin_required=True,
        notes="SKU Code field contains a UUID — must be ignored. "
              "Site code in parentheses at end of billing/shipping address.",
    ),

    "RRL": CustomerProfile(
        cluster="RRL",
        name="Reliance Retail",
        name_keywords=["reliance retail", "reliance fresh", "reliance smart", "milkbasket"],
        gstin_list=["36AABCR1718E1ZQ", "29AABCR1718E1ZL"],
        email_domains=["ril.com", "zmail.ril.com"],
        # Article No. is Reliance's own code (customer_sku), NOT HFL material code
        material_code_field="Article No.",
        ean_field="EAN No.",
        vendor_article_is_ean=True,  # "Vendor Article No." column = EAN barcode
        price_field="Base Cost",
        site_code_pattern="explicit_field",  # "Site: T1UL" in header
        vr01_strategy=VR01_EAN_PRIMARY,
        vr06_gstin_required=True,
        notes="NEVER map Article No. as HFL material code. "
              "Vendor Article No. = EAN. Site code as 'Site: XXXX'.",
    ),

    "DMT": CustomerProfile(
        cluster="DMT",
        name="DMart / Avenue Supermarts",
        name_keywords=["avenue supermarts", "dmart", "dmartindia", "d-mart"],
        gstin_list=["36AACCA8432H1ZR"],
        email_domains=["dmartindia.com"],
        # DMart has NO material code — EAN is the ONLY identifier
        material_code_field=None,
        ean_field="EAN No",
        price_field="L.Price",           # Landing Price (after discount)
        price_fallback_field="B.Price",
        discount_field="Sp.Dis%",
        site_code_pattern="ship_to_name",
        vr01_strategy=VR01_EAN_ONLY,
        vr06_gstin_required=True,
        notes="NO material code exists. Use L.Price (Landing Price) not B.Price. "
              "Ship-to store name used as site code.",
    ),

    "MORE": CustomerProfile(
        cluster="MORE",
        name="More Retail",
        name_keywords=["more retail", "more.co.in", "more supermarket"],
        gstin_list=["36AAACP2678Q1ZR", "29AAACP2678Q1ZM"],
        email_domains=["more.co.in"],
        # 'Primary Vendor SKU' column = HSN code (NOT the SKU — common mistake!)
        material_code_field="more. SKU",
        ean_field="Primary Barcode",
        price_field="Cost Price (INR)(excl TAX)",
        site_code_pattern="dc_number",   # 3-digit DC number at top of shipping block
        vr01_strategy=VR01_EAN_PRIMARY,
        vr06_gstin_required=True,
        notes="First column 'Primary Vendor SKU' = HSN code, NOT the SKU. "
              "Use 'more. SKU' column. DC number (e.g. 665/666) = site code.",
    ),

    "CVPL": CustomerProfile(
        cluster="CVPL",
        name="Cloudkart / Scootsy",
        name_keywords=["cloudkart", "scootsy"],
        gstin_list=["36AAKCC0275A1Z2"],
        email_domains=["scootsy.com", "cloudkart.com"],
        material_code_field="Item Code",   # Short integer (e.g. 24075)
        ean_field=None,                    # NO EAN in Cloudkart POs
        price_field="Unit Base Cost (INR)",
        site_code_pattern="gstin_based",   # GSTIN identifies which location
        vr01_strategy=VR01_CUSTOMER_SKU_PRIMARY,
        vr06_gstin_required=True,
        notes="No EAN column — description matching required for VR-01 fallback. "
              "GSTIN on PO identifies Hyderabad vs Kandlakoya location.",
    ),

    "BLK": CustomerProfile(
        cluster="BLK",
        name="Moonstone / Blinkit",
        name_keywords=["moonstone", "blinkit", "grofers"],
        gstin_list=["36AACFY8913A1Z9"],
        email_domains=["blinkit.com", "grofers.com"],
        material_code_field="Item Code",
        ean_field="Product UPC",
        price_field="Basic Cost Price",    # NOT 'Landing Rate' (that includes tax)
        site_code_pattern="store_name",
        vr01_strategy=VR01_EAN_PRIMARY,
        vr06_gstin_required=True,
        notes="Use Basic Cost Price, not Landing Rate. Landing Rate = basic + tax.",
    ),

    "LULU": CustomerProfile(
        cluster="LULU",
        name="Lulu Hypermarket",
        name_keywords=["lulu hypermarket", "lulu int shopping", "lulu int shoping", "lulu"],
        gstin_list=["36AABCL0212H1Z3"],
        email_domains=[],
        po_title_keywords=["purchase order(zl01)", "zl01"],
        material_code_field="Article",    # SAP ZL01 format
        ean_field="EAN",
        price_field="Net Price",          # NOT Gross Price (which is before discount)
        site_code_pattern="store_name",
        vr01_strategy=VR01_EAN_PRIMARY,
        vr06_gstin_required=True,
        notes="SAP ZL01 format. Use Net Price, not Gross Price.",
    ),

    "63IDEAS": CustomerProfile(
        cluster="63IDEAS",
        name="63Ideas / Scootsy Chennai",
        name_keywords=["63ideas", "63 ideas"],
        gstin_list=["33AAACZ8597L1ZJ"],
        email_domains=[],
        material_code_field=None,         # No code at all
        ean_field=None,
        price_field="Base Price (Rs)",
        site_code_pattern="address_only",
        vr01_strategy=VR01_DESCRIPTION_ONLY,
        vr06_gstin_required=False,        # Vendor GST often blank on their POs
        notes="No EAN, no material code — description fuzzy match only. "
              "Vendor GSTIN field often blank — do NOT hard-fail VR-06.",
    ),

    "SLVEG": CustomerProfile(
        cluster="SLVEG",
        name="SL Veggies India (Flipkart)",
        name_keywords=["sl veggies", "sl veggies india"],
        gstin_list=["36AAZCS5190H1ZL"],
        email_domains=[],
        material_code_field="FSN",        # Flipkart Serial Number — not mappable to HFL
        ean_field=None,
        price_field="Price",
        site_code_pattern="address_only",
        vr01_strategy=VR01_DESCRIPTION_ONLY,
        vr06_gstin_required=True,
        document_type_warning="May arrive as Heritage invoice/delivery note formatted as PO — check document title.",
        notes="FSN codes are Flipkart's internal codes, not useful for HFL mapping.",
    ),
}


# ══════════════════════════════════════════════════════════════════════════
# CUSTOMER-SPECIFIC EXTRACTION RULES (injected into LLM prompt)
# ══════════════════════════════════════════════════════════════════════════

CUSTOMER_EXTRACTION_RULES: dict[str, str] = {
    "ZEP": """
ZEPTO PO RULES:
- material_code = "Material Code" column value (this is HFL's own SAP code, e.g. 117705)
- ean = "EAN No" column (13-digit barcode starting with 890)
- IGNORE the "SKU Code" field entirely — it contains a UUID, not a usable code
- site_code: extract the value inside parentheses at the END of the billing/shipping address
  Example address: "HYD-BDE-MH-YAMJAL (HYD096M)" → site_code = "HYD096M"
- unit_price = "Base Cost" column (pre-tax)
""",

    "RRL": """
RELIANCE RETAIL PO RULES:
- article_code = "Article No." column → map to customer_sku (this is Reliance's internal code)
- ean = "EAN No." column OR "Vendor Article No." column (both contain the EAN barcode)
- NEVER use "Article No." as the HFL material code — it is NOT an HFL code
- material_code = null (leave empty — HFL code resolved via EAN lookup)
- unit_price = "Base Cost" column
- site_code: look for "Site:" label in the PO header, e.g. "Site: T1UL" → site_code = "T1UL"
""",

    "DMT": """
DMART (AVENUE SUPERMARTS) PO RULES:
- EAN is the ONLY product identifier — extract from "EAN No" column
- material_code = null (no HFL material code on DMart POs)
- article_code = null
- unit_price = "L.Price" column (Landing Price = net price after discount)
  DO NOT use "B.Price" — that is the base price before discount
- site_code: use the store name from the Ship-to address (e.g. "Khushaiguda Hyd DMart")
""",

    "MORE": """
MORE RETAIL PO RULES:
- CRITICAL: The first column labeled "Primary Vendor SKU" contains the HSN Code — DO NOT use as SKU
- customer_sku = "more. SKU" column (third column, e.g. 100055723)
- ean = "Primary Barcode" column (13-digit EAN)
- material_code = null (resolved via EAN lookup)
- unit_price = "Cost Price (INR)(excl TAX)" column
- site_code: look for a standalone 3-digit number at the TOP of the Shipping Address block
  This number (e.g. 665 or 666) is the DC (Distribution Centre) code
""",

    "CVPL": """
CLOUDKART / SCOOTSY PO RULES:
- material_code = "Item Code" column (short integer, e.g. 24075 or 2438)
- There is NO EAN column in Cloudkart POs — do not look for one
- unit_price = "Unit Base Cost (INR)" column
- site_code = null (location identified by buyer GSTIN)
""",

    "BLK": """
MOONSTONE / BLINKIT PO RULES:
- material_code = "Item Code" column
- ean = "Product UPC" column (13-digit barcode)
- unit_price = "Basic Cost Price" column
  DO NOT use "Landing Rate" — that includes tax and is not the NLC
- site_code: use the store/warehouse name from the delivery address
""",

    "LULU": """
LULU HYPERMARKET PO RULES (SAP ZL01 format):
- material_code = "Article" column
- ean = "EAN" column
- unit_price = "Net Price" column
  DO NOT use "Gross Price" — that is the pre-discount price
- site_code: use the store name from the delivery address
""",

    "63IDEAS": """
63IDEAS / SCOOTSY CHENNAI PO RULES:
- No material code exists on these POs — material_code = null
- No EAN column exists — ean = null
- Product matching relies entirely on description text
- unit_price = "Base Price (Rs)" column
- vendor_gstin may be blank on the PO — this is expected, set to null
- site_code = null
""",

    "SLVEG": """
SL VEGGIES INDIA (FLIPKART) PO RULES:
- This document may be titled "Heritage Invoice / Purchase Order" — treat it as a PO
- material_code / FSN = "FSN" column (Flipkart Serial Number — extract but note it is not an HFL code)
- No EAN column
- unit_price = "Price" column
- site_code = null
""",
}


# ══════════════════════════════════════════════════════════════════════════
# IDENTIFICATION ENGINE
# ══════════════════════════════════════════════════════════════════════════

def identify_customer(
    customer_name: str = "",
    gstin: str = "",
    email_sender: str = "",
    site_code: str = "",
    po_subject: str = "",
    po_title: str = "",
    db=None,
) -> CustomerProfile:
    """
    Identify the customer profile from available signals.

    Priority order (most → least reliable):
      1. GSTIN exact match          — definitive, globally unique
      2. Email domain match         — very reliable
      3. Site code DB lookup        — reliable if CustomerMapping is populated
      4. PO title keyword match     — reliable for format-specific POs (Lulu ZL01)
      5. Customer name keyword      — reliable but can have false positives
      6. Subject line keyword       — last resort

    Returns the matching CustomerProfile, or a generic fallback profile.
    Always logs which signal triggered the match for auditability.
    """
    # ── 1. GSTIN exact match ──────────────────────────────────────────────
    if gstin:
        clean_gstin = gstin.strip().upper()
        for cluster, profile in CUSTOMER_PROFILES.items():
            if clean_gstin in [g.upper() for g in profile.gstin_list]:
                logger.info(f"[IDENTIFY] GSTIN match → {cluster} ({profile.name})")
                return profile

    # ── 2. Email domain match ─────────────────────────────────────────────
    if email_sender and "@" in email_sender:
        domain = email_sender.split("@")[-1].lower().strip()
        for cluster, profile in CUSTOMER_PROFILES.items():
            if any(domain == d.lower() or domain.endswith("." + d.lower())
                   for d in profile.email_domains):
                logger.info(f"[IDENTIFY] Email domain match ({domain}) → {cluster}")
                return profile

    # ── 3. Site code lookup in CustomerMapping DB ─────────────────────────
    if site_code and db:
        try:
            from app.models.models import CustomerMapping
            rec = db.query(CustomerMapping).filter(
                CustomerMapping.site_code == str(site_code).strip()
            ).first()
            if rec and rec.cluster and rec.cluster in CUSTOMER_PROFILES:
                logger.info(f"[IDENTIFY] Site code match ({site_code}) → {rec.cluster}")
                return CUSTOMER_PROFILES[rec.cluster]
        except Exception as e:
            logger.warning(f"[IDENTIFY] Site code DB lookup failed: {e}")

    # ── 4. PO title keyword match ─────────────────────────────────────────
    title_lower = (po_title or po_subject or "").lower()
    if title_lower:
        for cluster, profile in CUSTOMER_PROFILES.items():
            if any(kw.lower() in title_lower for kw in profile.po_title_keywords):
                logger.info(f"[IDENTIFY] PO title match → {cluster}")
                return profile

    # ── 5. Customer name keyword match ────────────────────────────────────
    name_lower = (customer_name or "").lower().strip()
    if name_lower:
        # Longer keywords first to avoid "dmart" matching before "avenue supermarts"
        sorted_profiles = sorted(
            CUSTOMER_PROFILES.items(),
            key=lambda x: max((len(kw) for kw in x[1].name_keywords), default=0),
            reverse=True,
        )
        for cluster, profile in sorted_profiles:
            if any(kw.lower() in name_lower for kw in profile.name_keywords):
                logger.info(f"[IDENTIFY] Name keyword match ({customer_name!r}) → {cluster}")
                return profile

    # ── 6. Subject line fallback ──────────────────────────────────────────
    if po_subject:
        subject_lower = po_subject.lower()
        for cluster, profile in CUSTOMER_PROFILES.items():
            if any(kw.lower() in subject_lower for kw in profile.name_keywords):
                logger.info(f"[IDENTIFY] Subject line match → {cluster}")
                return profile

    # ── Fallback: unknown customer ────────────────────────────────────────
    logger.warning(
        f"[IDENTIFY] Could not identify customer — "
        f"name={customer_name!r} gstin={gstin!r} email={email_sender!r}"
    )
    return _generic_profile(customer_name)


def _generic_profile(customer_name: str = "") -> CustomerProfile:
    """Fallback profile for unknown customers — uses safest/most permissive settings."""
    cluster = customer_name.split()[0].upper()[:10] if customer_name else "UNKNOWN"
    return CustomerProfile(
        cluster=cluster,
        name=customer_name or "Unknown Customer",
        vr01_strategy=VR01_EAN_PRIMARY,
        vr06_gstin_required=True,
        notes="Auto-generated fallback profile — add to CUSTOMER_PROFILES for better extraction.",
    )


def get_extraction_rules_for_prompt(profile: CustomerProfile) -> str:
    """
    Return the customer-specific extraction rules block to inject into the LLM prompt.
    Returns empty string if no specific rules exist (generic baseline applies).
    """
    return CUSTOMER_EXTRACTION_RULES.get(profile.cluster, "")


def get_profile(cluster: str) -> Optional[CustomerProfile]:
    """Look up a profile by cluster code. Returns None if not found."""
    return CUSTOMER_PROFILES.get(cluster)


def list_all_profiles() -> list[CustomerProfile]:
    """Return all registered profiles (useful for admin UI / health checks)."""
    return list(CUSTOMER_PROFILES.values())