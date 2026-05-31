"""
Validation Engine — runs 6 sequential validation rules against extracted PO data.
Updated to use the real Heritage Foods mapping schema:
  - VR-01: ProductMapping keyed by sold_to_party + customer_sku/description
  - VR-02: PriceMaster keyed by sold_to_party + sales_district + sku_code, validates against NLC
  - VR-03: InventoryMaster keyed by hfl_sku_code
  - VR-04: CaseLotMaster keyed by cluster + sales_district + sku_code
  - VR-05: CustomerMapping keyed by site_code or address pattern
  - VR-06: GSTIN presence & format
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

logger = logging.getLogger(__name__)

PRICE_TOLERANCE = 5.0  # ₹5 tolerance for NLC validation


def run_validation(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    """
    Run all 6 validation rules. Returns (all_passed, summary_string).
    """
    all_passed = True
    failure_reasons = []

    # Reset all line items before re-validation
    for item in order.line_items:
        item.is_valid = True
        item.rejection_reason = None

    # VR-05 first — resolves ship_to_code & sales_district needed by VR-04
    if settings.RULE_VR05_LOCATION_MAPPING:
        passed, reason = _vr05_location_mapping(order, db)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    # VR-01: Product Mapping
    if settings.RULE_VR01_PRODUCT_MAPPING:
        passed, reason = _vr01_product_mapping(order, db)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    # VR-02: Price Validation (NLC)
    if settings.RULE_VR02_PRICE_VALIDATION:
        passed, reason = _vr02_price_validation(order, db)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    # VR-03: Inventory Check
    if settings.RULE_VR03_INVENTORY_CHECK:
        passed, reason = _vr03_inventory_check(order, db)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    # VR-04: Case Lot
    if settings.RULE_VR04_CASE_LOT:
        passed, reason = _vr04_case_lot(order, db)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    # VR-06: GSTIN
    if settings.RULE_VR06_GSTIN:
        passed, reason = _vr06_gstin(order, db)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    order.rejection_summary = " | ".join(failure_reasons) if failure_reasons else None
    return all_passed, order.rejection_summary or ""


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


# ── VR-01: Product Mapping ────────────────────────────────────────────────────

def _vr01_product_mapping(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    """
    Match each line item to a ProductMapping record.
    Lookup priority:
      1. sold_to_party + customer_sku (exact)
      2. sold_to_party + normalised description match
      3. hfl_sku_code direct match (if already resolved)
    """
    failed = []
    sold_to = order.sold_to_party or ""

    for item in order.line_items:
        matched = None

        # 1. Exact customer SKU match
        if item.customer_sku and sold_to:
            matched = db.query(ProductMapping).filter(
                ProductMapping.sold_to_party == sold_to,
                ProductMapping.customer_sku == str(item.customer_sku).strip()
            ).first()

        # 2. Normalised description match for this sold_to_party
        if not matched and item.description and sold_to:
            norm_desc = _normalize(item.description)
            candidates = db.query(ProductMapping).filter(
                ProductMapping.sold_to_party == sold_to
            ).all()
            for c in candidates:
                if c.customer_product_text and (
                    _normalize(c.customer_product_text) in norm_desc
                    or norm_desc in _normalize(c.customer_product_text)
                ):
                    matched = c
                    break

        # 3. If the extracted material_code already looks like an HFL SKU, confirm it
        if not matched and item.material_code:
            matched = db.query(ProductMapping).filter(
                ProductMapping.hfl_sku_code == str(item.material_code).strip()
            ).first()

        if matched:
            item.material_code = matched.hfl_sku_code
            if not item.description:
                item.description = matched.description
        else:
            item.is_valid = False
            desc_short = (item.description or item.customer_sku or "")[:50]
            item.rejection_reason = f"Unknown Product: '{desc_short}' not found for sold-to {sold_to or 'UNKNOWN'}"
            failed.append(item.id)

    if failed:
        return False, f"VR-01: {len(failed)} unknown product(s)"
    return True, ""


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

        # Try district-specific first
        price_rec = None
        if district:
            price_rec = db.query(PriceMaster).filter(
                PriceMaster.sold_to_party == sold_to,
                PriceMaster.sales_district == district,
                PriceMaster.sku_code == item.material_code
            ).first()

        # Fallback: any district for this sold_to + sku
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
            # Store NLC on line item for reference
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
    """
    Validate qty is a multiple of case lot.
    Keyed by cluster + sales_district + sku_code.
    """
    failed = []
    cluster = order.customer_code or ""
    district = order.sales_district or ""

    if not cluster or not district:
        return True, ""  # Cannot validate without these

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
      1. site_code exact match (vendor loc code on PO)
      2. sold_to_party match
      3. address pattern fuzzy match (LocationMapping fallback)
    Sets order.ship_to_code, order.sales_district, order.sales_office on success.
    """
    cluster = order.customer_code or ""

    # 1. Site code exact match
    if order.site_code:
        rec = db.query(CustomerMapping).filter(
            CustomerMapping.site_code == str(order.site_code).strip()
        ).first()
        if rec:
            _apply_customer_mapping(order, rec)
            return True, ""

    # 2. Sold-to party match
    if order.sold_to_party:
        rec = db.query(CustomerMapping).filter(
            CustomerMapping.sold_to_party == str(order.sold_to_party).strip()
        ).first()
        if rec:
            _apply_customer_mapping(order, rec)
            return True, ""

    # 3. Address fuzzy match against CustomerMapping.full_address
    if order.ship_to_address and cluster:
        norm_addr = _normalize(order.ship_to_address)
        candidates = db.query(CustomerMapping).filter(
            CustomerMapping.cluster == cluster
        ).all()
        for c in candidates:
            if c.full_address and _normalize(c.full_address) in norm_addr:
                _apply_customer_mapping(order, c)
                return True, ""

    # 4. Fallback: LocationMapping address patterns
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


def _apply_customer_mapping(order: OrderLedger, rec: CustomerMapping):
    """Apply resolved CustomerMapping to order fields."""
    order.ship_to_code = rec.ship_to_party_code
    order.sales_district = rec.sales_district
    order.sales_office = rec.sales_office
    if not order.sold_to_party:
        order.sold_to_party = rec.sold_to_party


# ── VR-06: GSTIN ─────────────────────────────────────────────────────────────

def _vr06_gstin(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    if not order.vendor_gstin:
        return False, "VR-06: Missing GSTIN on PO"
    gstin = order.vendor_gstin.strip()
    if len(gstin) != 15 or not gstin.isalnum():
        return False, f"VR-06: Invalid GSTIN format: {gstin}"
    return True, ""