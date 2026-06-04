"""
Validation Engine — Heritage Foods PO Automation
=================================================
Runs 6 sequential validation rules against extracted PO data.

VR-01 is now profile-driven: the lookup strategy (material_code / EAN /
customer_sku / description) is determined by the CustomerProfile for the
order's cluster, ensuring correct matching for all 9+ customers.

Rule overview:
  VR-01  Product mapping       — line item → HFL SKU code
  VR-02  Price validation      — unit price vs NLC (±₹5 tolerance)
  VR-03  Inventory check       — ordered qty ≤ unrestricted stock
  VR-04  Case lot              — qty is multiple of case lot
  VR-05  Location mapping      — ship-to resolved to SAP codes
  VR-06  GSTIN                 — presence & format (customer-profile-aware)
"""
import logging
from typing import Tuple
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.models import (
    OrderLedger, OrderLineItem,
    ProductMapping, PriceMaster, LocationMapping,
    InventoryMaster, CaseLotMaster, CustomerMapping
)
from app.services.customer_profiles import (
    get_profile,
    CustomerProfile,
    VR01_MATERIAL_CODE_PRIMARY,
    VR01_EAN_PRIMARY,
    VR01_EAN_ONLY,
    VR01_CUSTOMER_SKU_PRIMARY,
    VR01_DESCRIPTION_ONLY,
)

logger = logging.getLogger(__name__)

PRICE_TOLERANCE = 5.0   # ₹5 tolerance for NLC validation


def run_validation(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    """
    Run all 6 validation rules. Returns (all_passed, summary_string).
    VR-05 runs first to resolve ship_to_code + sales_district needed by VR-04.
    """
    all_passed = True
    failure_reasons = []

    # Reset line item validity before re-validation
    for item in order.line_items:
        item.is_valid = True
        item.rejection_reason = None

    # Resolve customer profile for profile-driven rules (VR-01, VR-06)
    profile = get_profile(order.customer_code or "")

    # VR-05 first — resolves ship_to_code & sales_district needed by VR-04
    if settings.RULE_VR05_LOCATION_MAPPING:
        passed, reason = _vr05_location_mapping(order, db)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    if settings.RULE_VR01_PRODUCT_MAPPING:
        passed, reason = _vr01_product_mapping(order, db, profile)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    if settings.RULE_VR02_PRICE_VALIDATION:
        passed, reason = _vr02_price_validation(order, db)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    if settings.RULE_VR03_INVENTORY_CHECK:
        passed, reason = _vr03_inventory_check(order, db)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    if settings.RULE_VR04_CASE_LOT:
        passed, reason = _vr04_case_lot(order, db)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    if settings.RULE_VR06_GSTIN:
        passed, reason = _vr06_gstin(order, db, profile)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    order.rejection_summary = " | ".join(failure_reasons) if failure_reasons else None
    return all_passed, order.rejection_summary or ""


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


# ── VR-01: Product Mapping ────────────────────────────────────────────────────

def _vr01_product_mapping(
    order: OrderLedger,
    db: Session,
    profile: CustomerProfile | None,
) -> Tuple[bool, str]:
    """
    Match each line item to a ProductMapping record.

    Lookup strategy is determined by the customer profile's vr01_strategy:

    VR01_MATERIAL_CODE_PRIMARY  (ZEP):
      material_code → ean → description

    VR01_EAN_PRIMARY  (RRL, MORE, BLK, LULU):
      ean → customer_sku → description

    VR01_EAN_ONLY  (DMT):
      ean only — raises EXCEPTION if no match (can't resolve without EAN)

    VR01_CUSTOMER_SKU_PRIMARY  (CVPL):
      customer_sku (for this sold_to_party) → description

    VR01_DESCRIPTION_ONLY  (63IDEAS, SLVEG):
      description fuzzy match only

    Unknown customers use VR01_EAN_PRIMARY as the safest default.
    """
    failed = []
    sold_to = order.sold_to_party or ""
    strategy = profile.vr01_strategy if profile else VR01_EAN_PRIMARY

    for item in order.line_items:
        matched = _lookup_product(item, sold_to, strategy, db)

        if matched:
            item.material_code = matched.hfl_sku_code
            if not item.description:
                item.description = matched.description
        else:
            item.is_valid = False
            ident = item.ean or item.material_code or item.customer_sku or item.description or "?"
            item.rejection_reason = (
                f"Unknown Product: '{str(ident)[:50]}' not found "
                f"(strategy={strategy}, sold-to={sold_to or 'UNKNOWN'})"
            )
            failed.append(item.id)

    if failed:
        return False, f"VR-01: {len(failed)} unknown product(s)"
    return True, ""


def _lookup_product(
    item: OrderLineItem,
    sold_to: str,
    strategy: str,
    db: Session,
) -> ProductMapping | None:
    """
    Attempt product lookup using the configured strategy chain.
    Each step falls through to the next if no match is found.
    """

    # ── Strategy: material_code primary ──────────────────────────────────
    if strategy == VR01_MATERIAL_CODE_PRIMARY:
        if item.material_code:
            m = db.query(ProductMapping).filter(
                ProductMapping.hfl_sku_code == str(item.material_code).strip()
            ).first()
            if m:
                return m

        # Fallback 1: EAN
        m = _lookup_by_ean(item.ean, db)
        if m:
            return m

        # Fallback 2: Description
        return _lookup_by_description(item.description, sold_to, db)

    # ── Strategy: EAN only (DMart) ────────────────────────────────────────
    if strategy == VR01_EAN_ONLY:
        return _lookup_by_ean(item.ean, db)

    # ── Strategy: EAN primary ─────────────────────────────────────────────
    if strategy == VR01_EAN_PRIMARY:
        m = _lookup_by_ean(item.ean, db)
        if m:
            return m

        # Fallback 1: customer_sku for this sold_to
        if item.customer_sku and sold_to:
            m = db.query(ProductMapping).filter(
                ProductMapping.sold_to_party == sold_to,
                ProductMapping.customer_sku == str(item.customer_sku).strip()
            ).first()
            if m:
                return m

        # Fallback 2: Description
        return _lookup_by_description(item.description, sold_to, db)

    # ── Strategy: customer_sku primary ───────────────────────────────────
    if strategy == VR01_CUSTOMER_SKU_PRIMARY:
        if item.customer_sku and sold_to:
            m = db.query(ProductMapping).filter(
                ProductMapping.sold_to_party == sold_to,
                ProductMapping.customer_sku == str(item.customer_sku).strip()
            ).first()
            if m:
                return m

        return _lookup_by_description(item.description, sold_to, db)

    # ── Strategy: description only ────────────────────────────────────────
    if strategy == VR01_DESCRIPTION_ONLY:
        return _lookup_by_description(item.description, sold_to, db)

    # ── Unknown strategy: try everything ─────────────────────────────────
    logger.warning(f"Unknown VR01 strategy '{strategy}' — trying all lookup paths")
    return (
        _lookup_by_ean(item.ean, db)
        or _lookup_by_description(item.description, sold_to, db)
    )


def _lookup_by_ean(ean: str | None, db: Session) -> ProductMapping | None:
    """Look up a product mapping by EAN (cross-customer — any sold_to_party)."""
    if not ean:
        return None
    clean_ean = str(ean).strip()
    return db.query(ProductMapping).filter(
        ProductMapping.ean == clean_ean
    ).first()


def _lookup_by_description(
    description: str | None,
    sold_to: str,
    db: Session,
) -> ProductMapping | None:
    """Fuzzy description match within a sold_to_party scope."""
    if not description:
        return None
    norm_desc = _normalize(description)

    # Try sold_to_party-scoped match first
    candidates = []
    if sold_to:
        candidates = db.query(ProductMapping).filter(
            ProductMapping.sold_to_party == sold_to
        ).all()

    # If no results (e.g. new customer with no mapping rows yet), search all
    if not candidates:
        candidates = db.query(ProductMapping).all()

    for c in candidates:
        if c.customer_product_text:
            norm_cpt = _normalize(c.customer_product_text)
            if norm_cpt in norm_desc or norm_desc in norm_cpt:
                return c
        if c.description:
            norm_cd = _normalize(c.description)
            if norm_cd in norm_desc or norm_desc in norm_cd:
                return c

    return None


# ── VR-02: Price Validation (NLC) ────────────────────────────────────────────

def _vr02_price_validation(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    """
    Validate unit price against NLC in PriceMaster.
    Keyed by sold_to_party + sales_district + sku_code.
    Falls back to sold_to_party + sku_code if no district record.
    """
    failed = []
    sold_to = order.sold_to_party or ""
    district = order.sales_district or ""

    for item in order.line_items:
        if not item.material_code or item.unit_price is None:
            continue

        price_rec = None
        if district:
            price_rec = db.query(PriceMaster).filter(
                PriceMaster.sold_to_party == sold_to,
                PriceMaster.sales_district == district,
                PriceMaster.sku_code == item.material_code
            ).first()

        if not price_rec:
            price_rec = db.query(PriceMaster).filter(
                PriceMaster.sold_to_party == sold_to,
                PriceMaster.sku_code == item.material_code
            ).first()

        if not price_rec:
            item.is_valid = False
            item.rejection_reason = (
                f"No Price Master Found for SKU {item.material_code} / "
                f"sold-to {sold_to or 'UNKNOWN'}"
            )
            failed.append(item.id)
        else:
            item.nlc = price_rec.nlc
            if abs(item.unit_price - price_rec.nlc) > PRICE_TOLERANCE:
                item.is_valid = False
                item.rejection_reason = (
                    f"Price Mismatch: PO ₹{item.unit_price:.2f} vs NLC ₹{price_rec.nlc:.2f} "
                    f"(tolerance ±₹{PRICE_TOLERANCE})"
                )
                failed.append(item.id)

    if failed:
        return False, f"VR-02: {len(failed)} price mismatch(es)"
    return True, ""


# ── VR-03: Inventory Check ────────────────────────────────────────────────────

def _vr03_inventory_check(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    """Sum stock across all plants for each HFL SKU code."""
    failed = []
    for item in order.line_items:
        if not item.material_code or item.qty is None:
            continue

        stock_records = db.query(InventoryMaster).filter(
            InventoryMaster.hfl_sku_code == item.material_code
        ).all()

        if not stock_records:
            continue  # No inventory record — skip (not a hard block)

        total_stock = sum(r.unrestricted_stock for r in stock_records)
        if item.qty > total_stock:
            item.is_valid = False
            item.rejection_reason = (
                f"Out of Stock: Ordered {item.qty} {item.uom or ''}, "
                f"Available {total_stock}"
            )
            failed.append(item.id)

    if failed:
        return False, f"VR-03: {len(failed)} item(s) out of stock"
    return True, ""


# ── VR-04: Case Lot ───────────────────────────────────────────────────────────

def _vr04_case_lot(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    """Validate qty is a multiple of the configured case lot."""
    failed = []
    cluster = order.customer_code or ""
    district = order.sales_district or ""

    if not cluster or not district:
        return True, ""

    for item in order.line_items:
        if not item.material_code or item.qty is None:
            continue

        case_lot = db.query(CaseLotMaster).filter(
            CaseLotMaster.cluster == cluster,
            CaseLotMaster.sales_district == district,
            CaseLotMaster.sku_code == item.material_code
        ).first()

        if not case_lot:
            continue

        if item.qty % case_lot.case_qty != 0:
            item.is_valid = False
            item.rejection_reason = (
                f"Case Lot Error: {item.qty} is not a multiple of "
                f"case qty {case_lot.case_qty}"
            )
            failed.append(item.id)

    if failed:
        return False, f"VR-04: {len(failed)} case lot violation(s)"
    return True, ""


# ── VR-05: Location Mapping ───────────────────────────────────────────────────

def _vr05_location_mapping(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    """
    Resolve ship-to details from CustomerMapping.
    Lookup priority:
      1. site_code exact match
      2. sold_to_party match
      3. Address fuzzy match (CustomerMapping)
      4. LocationMapping pattern fallback
    """
    cluster = order.customer_code or ""

    if order.site_code:
        rec = db.query(CustomerMapping).filter(
            CustomerMapping.site_code == str(order.site_code).strip()
        ).first()
        if rec:
            _apply_customer_mapping(order, rec)
            return True, ""

    if order.sold_to_party:
        rec = db.query(CustomerMapping).filter(
            CustomerMapping.sold_to_party == str(order.sold_to_party).strip()
        ).first()
        if rec:
            _apply_customer_mapping(order, rec)
            return True, ""

    if order.ship_to_address and cluster:
        norm_addr = _normalize(order.ship_to_address)
        candidates = db.query(CustomerMapping).filter(
            CustomerMapping.cluster == cluster
        ).all()
        for c in candidates:
            if c.full_address and _normalize(c.full_address) in norm_addr:
                _apply_customer_mapping(order, c)
                return True, ""

    if order.ship_to_address and cluster:
        norm_addr = _normalize(order.ship_to_address)
        loc_maps = db.query(LocationMapping).filter(
            LocationMapping.cluster == cluster
        ).all()
        for lm in loc_maps:
            if _normalize(lm.address_pattern) in norm_addr:
                order.ship_to_code = lm.sap_ship_to_code
                if lm.sales_district:
                    order.sales_district = lm.sales_district
                return True, ""

    order.ship_to_code = None
    return False, "VR-05: Cannot resolve ship-to location — site code / address not mapped"


def _apply_customer_mapping(order: OrderLedger, rec: CustomerMapping) -> None:
    order.ship_to_code = rec.ship_to_party_code
    order.sales_district = rec.sales_district
    order.sales_office = rec.sales_office
    if not order.sold_to_party:
        order.sold_to_party = rec.sold_to_party


# ── VR-06: GSTIN ─────────────────────────────────────────────────────────────

def _vr06_gstin(
    order: OrderLedger,
    db: Session,
    profile: CustomerProfile | None,
) -> Tuple[bool, str]:
    """
    Validate Heritage Foods' GSTIN is present on the PO.

    Respects the customer profile's vr06_gstin_required flag:
    - 63Ideas/Scootsy Chennai: vendor GSTIN is often blank by their system —
      flag as WARNING but do not hard-fail.
    - All other customers: missing GSTIN = hard failure.
    """
    gstin_required = profile.vr06_gstin_required if profile else True

    if not order.vendor_gstin:
        if not gstin_required:
            # Soft failure — log it but allow the order through
            logger.info(
                f"[VR-06] GSTIN missing for {order.po_number} "
                f"(customer {order.customer_code}) — allowed by profile"
            )
            return True, ""
        return False, "VR-06: Missing GSTIN on PO"

    gstin = order.vendor_gstin.strip()
    if len(gstin) != 15 or not gstin.isalnum():
        if not gstin_required:
            return True, ""
        return False, f"VR-06: Invalid GSTIN format: {gstin}"

    return True, ""