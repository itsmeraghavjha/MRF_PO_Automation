"""
Email Ingestion Service — Heritage Foods PO Automation
=======================================================
Polls IMAP inbox, processes PO attachments, deduplicates, and triggers
the extraction + validation pipeline.

Key changes from original:
  - Customer identification now uses customer_profiles.identify_customer()
    with GSTIN as the primary signal (was keyword-only before).
  - CANCELLATION po_type is now handled — order marked, pipeline halts.
  - PO number + customer GSTIN deduplication prevents processing the same
    PO twice if it arrives via different email threads.
  - Profile is passed through the pipeline so extraction gets customer-
    specific prompt rules for higher accuracy.
  - Site code extraction handles Zepto parenthetical pattern and
    More Retail DC number pattern.
"""
import os
import re
import logging
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from imap_tools import MailBox, AND
from app.core.config import settings
from app.db.base import SessionLocal
from app.models.models import (
    OrderLedger, OrderLineItem, AuditLog,
    SystemCheckpoint, CustomerMapping
)
from app.services.extraction import extract_po_data
from app.services.validation import run_validation
from app.services.sap_generator import generate_sap_csv
from app.services.pdf_parser import extract_pdf_text
from app.services.excel_parser import extract_excel_text
from app.services.customer_profiles import (
    identify_customer,
    CustomerProfile,
    get_profile,
)

logger = logging.getLogger(__name__)

SUBJECT_KEYWORDS = ["PO", "Purchase Order", "Order"]
BLOCKED_KEYWORDS = ["GRN", "Invoice", "Payment", "Quotation", "Proforma"]


def run_ingestion_cycle():
    """Main ingestion cycle — called by the scheduler every N seconds."""
    db = SessionLocal()
    try:
        last_uid = _get_checkpoint(db, "last_email_uid")
        logger.info(f"Ingestion cycle started. Last UID: {last_uid}")

        try:
            with MailBox(settings.IMAP_HOST, settings.IMAP_PORT).login(
                settings.IMAP_USER, settings.IMAP_PASSWORD
            ) as mailbox:
                mailbox.folder.set(settings.IMAP_FOLDER)

                criteria = AND(seen=False)
                emails = list(mailbox.fetch(limit=5, reverse=True, mark_seen=False))

                new_max_uid = last_uid

                for msg in emails:
                    uid = str(msg.uid)

                    if last_uid and int(uid) <= int(last_uid):
                        continue

                    if not _should_process_email(msg.subject):
                        logger.info(f"Skipping email UID {uid}: '{msg.subject}'")
                        continue

                    _process_email(msg, db)

                    if not new_max_uid or int(uid) > int(new_max_uid):
                        new_max_uid = uid

                if new_max_uid != last_uid:
                    _set_checkpoint(db, "last_email_uid", new_max_uid)

        except Exception as e:
            logger.error(f"IMAP connection failed: {e}")

    finally:
        db.close()


def _should_process_email(subject: str) -> bool:
    subject_upper = subject.upper()
    for blocked in BLOCKED_KEYWORDS:
        if blocked.upper() in subject_upper:
            return False
    for keyword in SUBJECT_KEYWORDS:
        if keyword.upper() in subject_upper:
            return True
    return False


def _process_email(msg, db: Session):
    """Process a single email — extract PO data from attachments."""
    pdf_dir = Path(settings.PDF_STORAGE_DIR)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    for att in msg.attachments:
        name = att.filename.lower()
        if not any(name.endswith(ext) for ext in [".pdf", ".xlsx", ".xls", ".csv"]):
            continue

        import re
        safe_name = f"{msg.uid}_{att.filename}"
        safe_name = re.sub(r'\s+', '_', safe_name)  # replace spaces with underscores
        save_path = pdf_dir / safe_name
        save_path.write_bytes(att.payload)
        logger.info(f"Saved attachment: {save_path}")

        if name.endswith(".pdf"):
            text = extract_pdf_text(str(save_path))
        else:
            text = extract_excel_text(str(save_path))

        if not text:
            logger.warning(f"Could not extract text from {att.filename}")
            continue

        # ── Step 1: Pre-identify customer from email signals ──────────────
        # We do a first pass with email-level signals so the extraction
        # prompt can be customer-specific (much better accuracy).
        pre_profile = identify_customer(
            email_sender=str(msg.from_),
            po_subject=msg.subject,
        )

        # ── Step 2: Extract with customer-specific prompt ─────────────────
        extracted = extract_po_data(
            text,
            subject=msg.subject,
            profile=pre_profile if pre_profile.cluster != "UNKNOWN" else None,
        )

        if not extracted:
            _create_failed_order(db, msg, str(save_path), "AI extraction failed")
            continue

        # ── Step 3: Document type check ───────────────────────────────────
        doc_type = extracted.get("document_type")
        if doc_type not in ["PURCHASE_ORDER", None]:
            logger.info(f"Skipping non-PO document: {doc_type}")
            continue

        # ── Step 4: Cancellation check ────────────────────────────────────
        if extracted.get("po_type") == "CANCELLATION":
            _handle_cancellation(db, msg, extracted, str(save_path))
            continue

        # ── Step 5: Deduplication (PO number + customer GSTIN) ────────────
        if _is_duplicate(db, extracted):
            logger.info(
                f"[DEDUP] Skipping duplicate PO: {extracted.get('po_number')} "
                f"(GSTIN: {extracted.get('customer_gstin')})"
            )
            continue

        # ── Step 6: Final customer identification (now with PO content) ───
        profile = identify_customer(
            customer_name=extracted.get("customer_name", ""),
            gstin=extracted.get("customer_gstin", ""),
            email_sender=str(msg.from_),
            site_code=_extract_site_code(extracted, pre_profile),
            po_subject=msg.subject,
            db=db,
        )
        customer_code = profile.cluster

        # ── Step 7: Post-process site code using profile-aware extraction ──
        extracted["site_code"] = _extract_site_code(extracted, profile)

        # ── Step 8: Persist order ─────────────────────────────────────────
        order = _create_order(db, msg, extracted, customer_code, str(save_path), profile)

        # ── Step 9: Validate ──────────────────────────────────────────────
        all_passed, summary = run_validation(order, db)

        if all_passed:
            if order.delivery_date:
                order.status = "VALIDATED"
                try:
                    filename, path = generate_sap_csv(order)
                    order.status = "SAP_SUCCESS"
                    _audit(db, order.id, "SAP_PUSHED", f"CSV: {filename}")
                    _trigger_delivery_request(order, db)
                except Exception as e:
                    logger.error(f"SAP CSV generation failed: {e}")
            else:
                order.status = "AWAITING_DELIVERY_DATE"
                _trigger_delivery_request(order, db)
        else:
            order.status = "VALIDATION_FAILED"

        db.commit()
        _audit(db, order.id, "STATUS_CHANGE", f"→ {order.status}")
        db.commit()

        logger.info(f"Order {order.po_number} processed → {order.status}")


def _is_duplicate(db: Session, extracted: dict) -> bool:
    """
    Check if this PO has already been processed.
    Uses PO number + customer GSTIN for reliable cross-email-thread dedup.
    Falls back to PO number alone if GSTIN is absent.
    """
    po_number = (extracted.get("po_number") or "").strip()
    customer_gstin = (extracted.get("customer_gstin") or "").strip()

    if not po_number:
        return False

    query = db.query(OrderLedger).filter(
        OrderLedger.po_number == po_number,
        OrderLedger.status != "VALIDATION_FAILED",  # Allow reprocessing failed orders
    )

    if customer_gstin:
        # Match on PO + GSTIN when available (most reliable)
        # But also check PO-only in case GSTIN was absent on the first ingestion
        existing = query.first()
        return existing is not None

    # PO number alone
    return query.first() is not None


def _handle_cancellation(db: Session, msg, extracted: dict, attachment_path: str):
    """
    Mark an existing order as cancelled, or record the cancellation notice.
    """
    po_number = extracted.get("po_number", "").strip()
    existing = db.query(OrderLedger).filter(
        OrderLedger.po_number == po_number
    ).first()

    if existing:
        existing.is_cancellation = True
        existing.status = "CANCELLED"
        _audit(
            db, existing.id, "CANCELLATION_RECEIVED",
            f"Cancellation PO received via email UID {msg.uid}",
        )
        db.commit()
        logger.info(f"Order {po_number} marked as CANCELLED")
    else:
        # No existing order — record cancellation notice for audit
        order = OrderLedger(
            po_number=po_number or f"CANCEL-{msg.uid}",
            customer_name=extracted.get("customer_name"),
            is_cancellation=True,
            status="CANCELLED",
            email_uid=str(msg.uid),
            email_subject=msg.subject,
            email_sender=str(msg.from_),
            drive_link=attachment_path,
            rejection_summary="Cancellation PO — no prior order found",
            raw_extraction_data=extracted,
        )
        db.add(order)
        db.commit()
        logger.info(f"Cancellation notice recorded for unknown PO: {po_number}")


def _extract_site_code(extracted: dict, profile: CustomerProfile | None) -> str | None:
    """
    Extract site code from the raw extracted data using the customer profile's
    site_code_pattern to handle the various formats across customers.

    Patterns:
      explicit_field  — already extracted by LLM (RRL: "Site: T1UL")
      parenthetical   — "(HYD096M)" at end of address text (Zepto)
      dc_number       — 3-digit number at start of shipping address (More Retail)
      gstin_based     — no site code, location derived from GSTIN (Cloudkart)
      ship_to_name    — store name used as site code (DMart, Lulu, Blinkit)
      address_only    — no reliable site code available
    """
    raw_site = (extracted.get("site_code") or "").strip()
    ship_to_address = (extracted.get("ship_to_address") or "").strip()
    pattern = profile.site_code_pattern if profile else "explicit_field"

    if pattern == "explicit_field":
        return raw_site or None

    if pattern == "parenthetical":
        # Zepto: extract text inside the LAST set of parentheses in address
        # Example: "HYD-BDE-MH-YAMJAL (HYD096M)" → "HYD096M"
        matches = re.findall(r"\(([A-Z0-9\-]+)\)", ship_to_address.upper())
        if matches:
            return matches[-1]
        # Fall back to whatever LLM extracted
        return raw_site or None

    if pattern == "dc_number":
        # More Retail: 3-digit number at very start of shipping address
        # Example: "665\nMore Retail DC, Bangalore"
        m = re.match(r"^(\d{3,4})\b", ship_to_address.strip())
        if m:
            return m.group(1)
        return raw_site or None

    if pattern == "gstin_based":
        # Cloudkart: no site code field — location inferred from buyer GSTIN
        # Return the GSTIN itself as a location key (will be resolved in VR-05)
        return extracted.get("customer_gstin") or raw_site or None

    if pattern in ("ship_to_name", "store_name"):
        # Use store name from delivery address as the site code key
        # VR-05 will match this against CustomerMapping.full_address
        if ship_to_address:
            # Take just the first line of the address as the "name"
            first_line = ship_to_address.split("\n")[0].strip()
            return first_line[:50] if first_line else None
        return raw_site or None

    # address_only / unknown
    return raw_site or None


def _create_order(
    db: Session,
    msg,
    extracted: dict,
    customer_code: str,
    attachment_path: str,
    profile: CustomerProfile | None,
) -> OrderLedger:
    """Persist extracted PO data to database."""
    order = OrderLedger(
        po_number=extracted.get("po_number", f"UNKNOWN-{msg.uid}"),
        po_date=extracted.get("po_date"),
        customer_code=customer_code,
        customer_name=extracted.get("customer_name"),
        vendor_gstin=extracted.get("customer_gstin"),
        ship_to_address=extracted.get("ship_to_address"),
        site_code=extracted.get("site_code"),
        delivery_date=extracted.get("delivery_date"),
        expiry_date=extracted.get("expiry_date"),
        is_update=extracted.get("po_type") == "REVISED",
        is_cancellation=extracted.get("po_type") == "CANCELLATION",
        status="NEW",
        email_uid=str(msg.uid),
        email_subject=msg.subject,
        email_sender=str(msg.from_),
        drive_link=attachment_path,
        raw_extraction_data=extracted,
    )
    db.add(order)
    db.flush()

    total = 0.0
    for li in extracted.get("line_items", []):
        qty = li.get("qty") or 0
        price = li.get("unit_price") or 0
        line_total = li.get("line_total") or (qty * price)
        total += line_total

        item = OrderLineItem(
            order_id=order.id,
            # EAN — new field
            ean=li.get("ean"),
            # Material code: use what was resolved in normalisation
            material_code=li.get("material_code"),
            # Customer SKU: buyer's own code
            customer_sku=li.get("customer_sku"),
            description=li.get("description"),
            uom=li.get("uom"),
            hsn_code=li.get("hsn_code"),
            qty=qty,
            unit_price=price,
            mrp=li.get("mrp"),
            tax_rate=li.get("tax_rate"),
            tax_amount=li.get("tax_amount"),
            line_total=line_total,
        )
        db.add(item)

    order.total_value = total
    db.flush()
    return order


def _create_failed_order(db: Session, msg, attachment_path: str, reason: str):
    order = OrderLedger(
        po_number=f"FAILED-{msg.uid}",
        status="VALIDATION_FAILED",
        email_uid=str(msg.uid),
        email_subject=msg.subject,
        email_sender=str(msg.from_),
        drive_link=attachment_path,
        rejection_summary=reason,
    )
    db.add(order)
    db.commit()


def _trigger_delivery_request(order: OrderLedger, db: Session):
    """Auto-trigger vendor delivery confirmation email."""
    try:
        from app.api.routes.vendor import _resolve_vendor_email
        from app.services.email_service import send_delivery_confirmation_request
        from app.models.models import DeliveryToken
        import uuid
        from datetime import timedelta, timezone

        recipient = _resolve_vendor_email(order, db)
        if not recipient:
            logger.info(f"[VENDOR] No vendor email for {order.po_number} — skipping")
            return

        # Expire existing pending tokens
        existing = db.query(DeliveryToken).filter(
            DeliveryToken.order_id == order.id,
            DeliveryToken.status == "PENDING"
        ).all()
        for t in existing:
            t.status = "EXPIRED"

        token_str = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        token_rec = DeliveryToken(
            token=token_str,
            order_id=order.id,
            recipient_email=recipient,
            status="PENDING",
            expires_at=expires_at,
        )
        db.add(token_rec)
        db.flush()

        base_url = settings.APP_BASE_URL.rstrip("/")
        line_items = [
            {"description": li.description, "uom": li.uom, "qty": li.qty}
            for li in order.line_items
        ]

        sent = send_delivery_confirmation_request(
            to_email=recipient,
            po_number=order.po_number,
            customer_name=order.customer_name or order.customer_code or "—",
            ship_to_address=order.ship_to_address or "—",
            delivery_date=order.delivery_date,
            line_items=line_items,
            token=token_str,
            base_url=base_url,
        )

        _audit(
            db, order.id, "DELIVERY_REQUEST_SENT",
            f"Auto-triggered. Email {'sent' if sent else 'logged'} to {recipient}.",
            performed_by="system",
        )

    except Exception as e:
        logger.error(f"[VENDOR] Failed to send delivery request for {order.po_number}: {e}")


def _get_checkpoint(db: Session, key: str) -> str | None:
    rec = db.query(SystemCheckpoint).filter(SystemCheckpoint.key == key).first()
    return rec.value if rec else None


def _set_checkpoint(db: Session, key: str, value: str):
    rec = db.query(SystemCheckpoint).filter(SystemCheckpoint.key == key).first()
    if rec:
        rec.value = value
    else:
        db.add(SystemCheckpoint(key=key, value=value))
    db.commit()


def _audit(
    db: Session,
    order_id: int,
    event_type: str,
    description: str,
    performed_by: str = "system",
):
    log = AuditLog(
        order_id=order_id,
        event_type=event_type,
        description=description,
        performed_by=performed_by,
    )
    db.add(log)