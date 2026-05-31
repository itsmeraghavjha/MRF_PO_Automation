"""
Email Ingestion Service — polls IMAP inbox, processes PO attachments,
deduplicates by UID checkpoint, and triggers the extraction + validation pipeline.

Phase 3 additions:
  - Auto-sends delivery confirmation request when status = AWAITING_DELIVERY_DATE
  - Fixed _resolve_customer_code() — was referencing non-existent variation_name column
"""
import os
import io
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

        safe_name = f"{msg.uid}_{att.filename}"
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

        extracted = extract_po_data(text, subject=msg.subject)

        if not extracted:
            _create_failed_order(db, msg, str(save_path), "AI extraction failed")
            continue

        if extracted.get("document_type") not in ["PURCHASE_ORDER", None]:
            logger.info(f"Skipping non-PO document: {extracted.get('document_type')}")
            continue

        customer_code = _resolve_customer_code(
            extracted.get("customer_name", ""),
            extracted.get("site_code"),
            db
        )

        order = _create_order(db, msg, extracted, customer_code, str(save_path))

        all_passed, summary = run_validation(order, db)

        if all_passed:
            if order.delivery_date:
                order.status = "VALIDATED"
                try:
                    filename, path = generate_sap_csv(order)
                    order.status = "SAP_SUCCESS"
                    _audit(db, order.id, "SAP_PUSHED", f"CSV: {filename}")
                    # ── Phase 3: send delivery confirmation after SAP push ──
                    _trigger_delivery_request(order, db, msg)
                except Exception as e:
                    logger.error(f"SAP CSV generation failed: {e}")
            else:
                order.status = "AWAITING_DELIVERY_DATE"
                # ── Phase 3: send delivery confirmation when date is missing ──
                _trigger_delivery_request(order, db, msg)
        else:
            order.status = "VALIDATION_FAILED"

        db.commit()
        _audit(db, order.id, "STATUS_CHANGE", f"→ {order.status}")
        db.commit()

        logger.info(f"Order {order.po_number} processed → {order.status}")


def _trigger_delivery_request(order: OrderLedger, db: Session, msg=None):
    """
    Auto-trigger a vendor delivery confirmation email.
    Called after SAP push (SAP_SUCCESS) or when delivery date is absent (AWAITING_DELIVERY_DATE).
    Uses a fake request object since we're not in an HTTP context.
    """
    try:
        from app.api.routes.vendor import _resolve_vendor_email
        from app.services.email_service import send_delivery_confirmation_request
        from app.models.models import DeliveryToken
        import uuid
        from datetime import timedelta, timezone

        recipient = _resolve_vendor_email(order, db)
        if not recipient:
            logger.info(f"[VENDOR] No vendor email for order {order.po_number} — skipping delivery request")
            return

        # Expire existing tokens
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
            f"Auto-triggered. Email {'sent' if sent else 'logged'} to {recipient}. Token: {token_str[:8]}…",
            performed_by="system"
        )
        logger.info(f"[VENDOR] Delivery request {'sent' if sent else 'logged'} for {order.po_number} → {recipient}")

    except Exception as e:
        logger.error(f"[VENDOR] Failed to send delivery request for {order.po_number}: {e}")


def _resolve_customer_code(customer_name: str, site_code: str | None, db: Session) -> str:
    """
    Normalize customer name → canonical cluster code.

    BUG FIX: Original code referenced m.variation_name which doesn't exist.
    Now uses cluster + full_address matching from CustomerMapping.
    """
    if not customer_name and not site_code:
        return "UNKNOWN"

    # 1. Site code exact match (most reliable)
    if site_code:
        rec = db.query(CustomerMapping).filter(
            CustomerMapping.site_code == str(site_code).strip()
        ).first()
        if rec and rec.cluster:
            return rec.cluster

    # 2. Fuzzy match customer name against cluster values and full_address
    if customer_name:
        normalized = customer_name.lower().strip()

        # Check cluster names (e.g. "Reliance" → "RRL")
        CLUSTER_KEYWORDS = {
            "reliance": "RRL",
            "dmart": "DMT",
            "avenue supermarts": "DMT",
            "bigbasket": "BBK",
            "zepto": "ZEP",
            "amazon": "AMZ",
            "walmart": "WMT",
            "flipkart": "FLK",
            "swiggy": "SWG",
            "blinkit": "BLK",
        }
        for keyword, code in CLUSTER_KEYWORDS.items():
            if keyword in normalized:
                return code

        # 3. Match against CustomerMapping.full_address or cluster
        all_mappings = db.query(CustomerMapping).all()
        for m in all_mappings:
            if m.full_address and any(
                word in m.full_address.lower()
                for word in normalized.split()
                if len(word) > 3
            ):
                return m.cluster or "UNKNOWN"

    # 4. Fallback: first word uppercased
    if customer_name:
        return customer_name.split()[0].upper()[:10]

    return "UNKNOWN"


def _create_order(db: Session, msg, extracted: dict, customer_code: str, attachment_path: str) -> OrderLedger:
    """Persist extracted PO data to database."""
    order = OrderLedger(
        po_number=extracted.get("po_number", f"UNKNOWN-{msg.uid}"),
        po_date=extracted.get("po_date"),
        customer_code=customer_code,
        customer_name=extracted.get("customer_name"),
        vendor_gstin=extracted.get("vendor_gstin"),
        ship_to_address=extracted.get("ship_to_address"),
        site_code=extracted.get("site_code"),
        delivery_date=extracted.get("delivery_date"),
        expiry_date=extracted.get("expiry_date"),
        is_update=extracted.get("po_type") == "REVISED",
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
            material_code=li.get("material_code") or li.get("vendor_article_code") or li.get("article_code"),
            customer_sku=li.get("customer_sku") or li.get("article_code"),
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


def _get_checkpoint(db: Session, key: str) -> str:
    rec = db.query(SystemCheckpoint).filter(SystemCheckpoint.key == key).first()
    return rec.value if rec else None


def _set_checkpoint(db: Session, key: str, value: str):
    rec = db.query(SystemCheckpoint).filter(SystemCheckpoint.key == key).first()
    if rec:
        rec.value = value
    else:
        db.add(SystemCheckpoint(key=key, value=value))
    db.commit()


def _audit(db: Session, order_id: int, event_type: str, description: str, performed_by: str = "system"):
    log = AuditLog(
        order_id=order_id,
        event_type=event_type,
        description=description,
        performed_by=performed_by
    )
    db.add(log)