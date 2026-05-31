"""
Validation Engine — runs 6 sequential validation rules against extracted PO data.
Each rule is independently togglable via config. Failures are tracked per line item.
"""
import logging
from typing import List, Tuple
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.models import (
    OrderLedger, OrderLineItem,
    ProductMapping, PriceMaster, LocationMapping,
    InventoryMaster, CaseLotMaster, DistrictMapping
)

logger = logging.getLogger(__name__)

PRICE_TOLERANCE = 5.0  # ₹5 tolerance for price validation


def run_validation(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    """
    Run all 6 validation rules against an order.
    Returns (all_passed: bool, summary: str)
    """
    all_passed = True
    failure_reasons = []

    # Reset all line items to valid before re-validation
    for item in order.line_items:
        item.is_valid = True
        item.rejection_reason = None

    # VR-01: Product Mapping
    if settings.RULE_VR01_PRODUCT_MAPPING:
        passed, reason = _vr01_product_mapping(order, db)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    # VR-05: Location Mapping (resolve ship_to_code first — needed for VR-04)
    if settings.RULE_VR05_LOCATION_MAPPING:
        passed, reason = _vr05_location_mapping(order, db)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    # VR-02: Price Validation
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

    # VR-04: Case Lot Validation
    if settings.RULE_VR04_CASE_LOT:
        passed, reason = _vr04_case_lot(order, db)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    # VR-06: GSTIN Presence
    if settings.RULE_VR06_GSTIN:
        passed, reason = _vr06_gstin(order, db)
        if not passed:
            all_passed = False
            failure_reasons.append(reason)

    order.rejection_summary = " | ".join(failure_reasons) if failure_reasons else None
    return all_passed, order.rejection_summary or ""


def _normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching."""
    return " ".join(text.lower().strip().split())


def _vr01_product_mapping(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    """Match each line item description to a SAP material code."""
    failed_items = []

    for item in order.line_items:
        if not item.description:
            item.is_valid = False
            item.rejection_reason = "Unknown Product: No description provided"
            failed_items.append(item.id)
            continue

        # Try exact match first, then normalized
        normalized_desc = _normalize_text(item.description)

        mapping = db.query(ProductMapping).filter(
            ProductMapping.customer_code == order.customer_code
        ).all()

        matched = None
        for m in mapping:
            if _normalize_text(m.customer_product_text) in normalized_desc or \
               normalized_desc in _normalize_text(m.customer_product_text):
                matched = m
                break

        # Also try article code match
        if not matched and item.material_code:
            matched = db.query(ProductMapping).filter(
                ProductMapping.sap_material_code == item.material_code
            ).first()

        if matched:
            item.material_code = matched.sap_material_code
            if not item.description:
                item.description = matched.sap_product_description
        else:
            item.is_valid = False
            item.rejection_reason = f"Unknown Product: '{item.description[:50]}' not found in mapping"
            failed_items.append(item.id)

    if failed_items:
        return False, f"VR-01: {len(failed_items)} unknown product(s)"
    return True, ""


def _vr02_price_validation(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    """Compare extracted unit price against PriceMaster with ±₹5 tolerance."""
    failed_items = []

    for item in order.line_items:
        if not item.material_code or item.unit_price is None:
            continue

        price_record = db.query(PriceMaster).filter(
            PriceMaster.customer_code == order.customer_code,
            PriceMaster.sap_material_code == item.material_code
        ).first()

        if not price_record:
            item.is_valid = False
            item.rejection_reason = f"No Price Master Found for {item.material_code} / {order.customer_code}"
            failed_items.append(item.id)
        elif abs(item.unit_price - price_record.approved_price) > PRICE_TOLERANCE:
            item.is_valid = False
            item.rejection_reason = (
                f"Price Mismatch: PO ₹{item.unit_price:.2f} vs Master ₹{price_record.approved_price:.2f} "
                f"(tolerance ±₹{PRICE_TOLERANCE})"
            )
            failed_items.append(item.id)

    if failed_items:
        return False, f"VR-02: {len(failed_items)} price mismatch(es)"
    return True, ""


def _vr03_inventory_check(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    """Check if ordered quantity exceeds available unrestricted stock."""
    failed_items = []

    for item in order.line_items:
        if not item.material_code or item.qty is None:
            continue

        # Sum stock across all plants for this material
        stock_records = db.query(InventoryMaster).filter(
            InventoryMaster.sap_material_code == item.material_code
        ).all()

        if not stock_records:
            continue  # No inventory record — skip (not a hard block by default)

        total_stock = sum(r.unrestricted_stock for r in stock_records)

        if item.qty > total_stock:
            item.is_valid = False
            item.rejection_reason = (
                f"Out of Stock: Ordered {item.qty} {item.uom}, "
                f"Available {total_stock} {item.uom}"
            )
            failed_items.append(item.id)

    if failed_items:
        return False, f"VR-03: {len(failed_items)} item(s) out of stock"
    return True, ""


def _vr04_case_lot(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    """Validate ordered quantity is a valid multiple of case lot quantity."""
    failed_items = []

    if not order.ship_to_code:
        return True, ""  # Can't validate without ship_to_code

    # Get sales district for this ship_to_code
    district_rec = db.query(DistrictMapping).filter(
        DistrictMapping.ship_to_code == order.ship_to_code
    ).first()

    if not district_rec:
        return True, ""  # No district mapping — skip

    for item in order.line_items:
        if not item.material_code or item.qty is None:
            continue

        case_lot = db.query(CaseLotMaster).filter(
            CaseLotMaster.sap_material_code == item.material_code,
            CaseLotMaster.sales_district == district_rec.sales_district
        ).first()

        if not case_lot:
            continue

        if item.qty % case_lot.case_qty != 0:
            item.is_valid = False
            item.rejection_reason = (
                f"Case Lot Error: {item.qty} is not a multiple of case qty {case_lot.case_qty}"
            )
            failed_items.append(item.id)

    if failed_items:
        return False, f"VR-04: {len(failed_items)} case lot violation(s)"
    return True, ""


def _vr05_location_mapping(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    """Resolve ship-to address to SAP ship-to party code."""
    if not order.ship_to_address:
        order.ship_to_code = None
        return False, "VR-05: No ship-to address on PO"

    normalized_addr = _normalize_text(order.ship_to_address)

    mappings = db.query(LocationMapping).filter(
        LocationMapping.customer_code == order.customer_code
    ).all()

    for mapping in mappings:
        if _normalize_text(mapping.address_pattern) in normalized_addr:
            order.ship_to_code = mapping.sap_ship_to_code
            return True, ""

    # Not found
    order.ship_to_code = None
    return False, f"VR-05: Unknown Location — ship-to address not mapped"


def _vr06_gstin(order: OrderLedger, db: Session) -> Tuple[bool, str]:
    """Verify vendor GSTIN is present and correctly formatted."""
    if not order.vendor_gstin:
        return False, "VR-06: Missing GSTIN on PO"

    gstin = order.vendor_gstin.strip()
    if len(gstin) != 15 or not gstin.isalnum():
        return False, f"VR-06: Invalid GSTIN format: {gstin}"

    return True, ""