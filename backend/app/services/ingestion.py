"""
Email Ingestion Service — polls IMAP inbox, processes PO attachments,
deduplicates by UID checkpoint, and triggers the extraction + validation pipeline.
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
from app.models.models import OrderLedger, OrderLineItem, AuditLog, SystemCheckpoint, CustomerMapping
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

                # Fetch emails newer than last checkpoint
                criteria = AND(seen=False)
                emails = list(mailbox.fetch(limit=5, reverse=True, mark_seen=False))

                new_max_uid = last_uid

                for msg in emails:
                    uid = str(msg.uid)

                    if last_uid and int(uid) <= int(last_uid):
                        continue  # Already processed

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
    """Check subject against keyword filters."""
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

        # Save attachment
        safe_name = f"{msg.uid}_{att.filename}"
        save_path = pdf_dir / safe_name
        save_path.write_bytes(att.payload)
        logger.info(f"Saved attachment: {save_path}")

        # Extract text
        if name.endswith(".pdf"):
            text = extract_pdf_text(str(save_path))
        else:
            text = extract_excel_text(str(save_path))

        if not text:
            logger.warning(f"Could not extract text from {att.filename}")
            continue

        # AI extraction
        extracted = extract_po_data(text, subject=msg.subject)

        if not extracted:
            _create_failed_order(db, msg, str(save_path), "AI extraction failed")
            continue

        # Reject non-PO documents
        if extracted.get("document_type") not in ["PURCHASE_ORDER", None]:
            logger.info(f"Skipping non-PO document: {extracted.get('document_type')}")
            continue

        # Resolve customer code
        customer_code = _resolve_customer_code(
            extracted.get("customer_name", ""), db
        )

        # Create order record
        order = _create_order(db, msg, extracted, customer_code, str(save_path))

        # Run validation
        all_passed, summary = run_validation(order, db)

        if all_passed:
            if order.delivery_date:
                order.status = "VALIDATED"
                # Auto-push SAP CSV
                try:
                    filename, path = generate_sap_csv(order)
                    order.status = "SAP_SUCCESS"
                    _audit(db, order.id, "SAP_PUSHED", f"CSV: {filename}")
                except Exception as e:
                    logger.error(f"SAP CSV generation failed: {e}")
            else:
                order.status = "AWAITING_DELIVERY_DATE"
        else:
            order.status = "VALIDATION_FAILED"

        db.commit()
        _audit(db, order.id, "STATUS_CHANGE", f"→ {order.status}")
        db.commit()

        logger.info(f"Order {order.po_number} processed → {order.status}")


def _resolve_customer_code(customer_name: str, db: Session) -> str:
    """Normalize customer name to canonical code."""
    if not customer_name:
        return "UNKNOWN"

    mappings = db.query(CustomerMapping).all()
    normalized = customer_name.lower().strip()

    for m in mappings:
        if m.variation_name.lower() in normalized or normalized in m.variation_name.lower():
            return m.normalized_code

    # Fallback: use first word uppercased
    return customer_name.split()[0].upper()[:10] if customer_name else "UNKNOWN"


def _create_order(db: Session, msg, extracted: dict, customer_code: str, attachment_path: str) -> OrderLedger:
    """Persist extracted PO data to database."""
    order = OrderLedger(
        po_number=extracted.get("po_number", f"UNKNOWN-{msg.uid}"),
        po_date=extracted.get("po_date"),
        customer_code=customer_code,
        customer_name=extracted.get("customer_name"),
        vendor_gstin=extracted.get("vendor_gstin"),
        ship_to_address=extracted.get("ship_to_address"),
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
            material_code=li.get("article_code"),
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
    """Create a failed order record for emails that couldn't be processed."""
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
    log = AuditLog(order_id=order_id, event_type=event_type, description=description, performed_by=performed_by)
    db.add(log)