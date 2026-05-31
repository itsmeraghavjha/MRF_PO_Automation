"""
Vendor Delivery Portal — Phase 3
Endpoints:
  POST /api/v1/orders/{order_id}/send-delivery-request  — generate token + send email
  GET  /vendor/{token}                                   — mobile-friendly portal page
  POST /vendor/{token}/confirm                           — submit delivery date
  GET  /api/v1/vendor/token-status/{token}               — ops UI status check
"""
import uuid
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.db.base import get_db
from app.models.models import OrderLedger, DeliveryToken, AuditLog
from app.services.email_service import send_delivery_confirmation_request

logger = logging.getLogger(__name__)

# ── Internal API router (mounted under /api/v1) ───────────────────────────
api_router = APIRouter(tags=["vendor"])

# ── Vendor portal router (mounted at root /) ──────────────────────────────
portal_router = APIRouter(tags=["vendor-portal"])

TOKEN_EXPIRY_DAYS = 7
CUTOFF_HOURS = 36  # read-only after this many hours before delivery


# ── Helpers ───────────────────────────────────────────────────────────────

def _get_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _is_within_cutoff(delivery_date_str: str | None) -> bool:
    """Return True if we are PAST the 36-hour cutoff (i.e. editing is locked)."""
    if not delivery_date_str:
        return False
    try:
        delivery_dt = datetime.strptime(delivery_date_str, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        cutoff_dt = delivery_dt - timedelta(hours=CUTOFF_HOURS)
        return datetime.now(timezone.utc) >= cutoff_dt
    except Exception:
        return False


def _token_valid(token_rec: DeliveryToken) -> tuple[bool, str]:
    """Returns (is_valid, reason_if_invalid)."""
    if token_rec.status == "EXPIRED":
        return False, "This confirmation link has expired."
    if token_rec.expires_at and datetime.now(timezone.utc) > token_rec.expires_at.replace(tzinfo=timezone.utc):
        token_rec.status = "EXPIRED"
        return False, "This confirmation link has expired."
    return True, ""


# ══════════════════════════════════════════════════════════════════════════
# INTERNAL API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════

@api_router.post("/orders/{order_id}/send-delivery-request")
def send_delivery_request(
    order_id: int,
    request: Request,
    performed_by: str = "ops_user",
    db: Session = Depends(get_db),
):
    """
    Generate a DeliveryToken and email the vendor a confirmation link.
    Can be called:
      - Automatically by ingestion when status = AWAITING_DELIVERY_DATE
      - Manually by ops staff from the exception portal
    """
    order = db.query(OrderLedger).filter(OrderLedger.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Determine recipient email — prefer CustomerMapping contact, fallback to email_sender
    recipient = _resolve_vendor_email(order, db)
    if not recipient:
        raise HTTPException(
            status_code=400,
            detail="No vendor email address found. Add one in Customer Mapping."
        )

    # Expire any existing pending tokens for this order
    existing = db.query(DeliveryToken).filter(
        DeliveryToken.order_id == order_id,
        DeliveryToken.status == "PENDING"
    ).all()
    for t in existing:
        t.status = "EXPIRED"

    # Create new token
    token_str = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRY_DAYS)
    token_rec = DeliveryToken(
        token=token_str,
        order_id=order_id,
        recipient_email=recipient,
        status="PENDING",
        expires_at=expires_at,
    )
    db.add(token_rec)
    db.flush()

    # Send email
    base_url = _get_base_url(request)
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

    # Update order status
    if order.status == "VALIDATED":
        order.status = "AWAITING_DELIVERY_DATE"

    # Audit
    audit = AuditLog(
        order_id=order_id,
        event_type="DELIVERY_REQUEST_SENT",
        description=f"Confirmation email {'sent' if sent else 'logged (SMTP not configured)'} to {recipient}. Token: {token_str[:8]}…",
        performed_by=performed_by,
    )
    db.add(audit)
    db.commit()

    return {
        "success": True,
        "token": token_str,
        "recipient": recipient,
        "email_sent": sent,
        "expires_at": expires_at.isoformat(),
        "portal_url": f"{base_url}/vendor/{token_str}",
    }


@api_router.get("/vendor/token-status/{token}")
def get_token_status(token: str, db: Session = Depends(get_db)):
    """Ops dashboard: check status of a delivery token."""
    rec = db.query(DeliveryToken).filter(DeliveryToken.token == token).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Token not found")
    order = db.query(OrderLedger).filter(OrderLedger.id == rec.order_id).first()
    return {
        "token": token[:8] + "…",
        "order_id": rec.order_id,
        "po_number": order.po_number if order else None,
        "recipient_email": rec.recipient_email,
        "status": rec.status,
        "expires_at": rec.expires_at,
        "created_at": rec.created_at,
        "current_delivery_date": order.delivery_date if order else None,
    }


# ══════════════════════════════════════════════════════════════════════════
# VENDOR PORTAL — server-rendered HTML pages
# ══════════════════════════════════════════════════════════════════════════

@portal_router.get("/vendor/{token}", response_class=HTMLResponse)
def vendor_portal(token: str, request: Request, db: Session = Depends(get_db)):
    """Mobile-friendly vendor delivery confirmation portal."""
    token_rec = db.query(DeliveryToken).filter(DeliveryToken.token == token).first()

    if not token_rec:
        return HTMLResponse(_error_page("Invalid Link", "This confirmation link is not valid or has already been used."), status_code=404)

    valid, reason = _token_valid(token_rec)
    if not valid:
        db.commit()
        return HTMLResponse(_error_page("Link Expired", reason))

    order = db.query(OrderLedger).filter(OrderLedger.id == token_rec.order_id).first()
    if not order:
        return HTMLResponse(_error_page("Order Not Found", "The order associated with this link could not be found."), status_code=404)

    # Mark as visited
    if token_rec.status == "PENDING":
        token_rec.status = "VISITED"
        db.commit()

    locked = _is_within_cutoff(order.delivery_date)
    return HTMLResponse(_portal_page(order, token, locked, success=False))


@portal_router.post("/vendor/{token}/confirm", response_class=HTMLResponse)
async def vendor_confirm(token: str, request: Request, db: Session = Depends(get_db)):
    """Process delivery date submission from vendor portal."""
    token_rec = db.query(DeliveryToken).filter(DeliveryToken.token == token).first()

    if not token_rec:
        return HTMLResponse(_error_page("Invalid Link", "This confirmation link is not valid."), status_code=404)

    valid, reason = _token_valid(token_rec)
    if not valid:
        db.commit()
        return HTMLResponse(_error_page("Link Expired", reason))

    order = db.query(OrderLedger).filter(OrderLedger.id == token_rec.order_id).first()
    if not order:
        return HTMLResponse(_error_page("Order Not Found", ""), status_code=404)

    # Check cutoff AGAIN server-side (cannot trust client)
    if _is_within_cutoff(order.delivery_date):
        return HTMLResponse(_portal_page(order, token, locked=True, success=False,
                                          error="The 36-hour modification cutoff has passed. No changes can be made."))

    # Parse form
    form = await request.form()
    new_date = form.get("delivery_date", "").strip()

    if not new_date:
        return HTMLResponse(_portal_page(order, token, locked=False, success=False,
                                          error="Please select a delivery date."))

    # Validate date format
    try:
        datetime.strptime(new_date, "%Y-%m-%d")
    except ValueError:
        return HTMLResponse(_portal_page(order, token, locked=False, success=False,
                                          error="Invalid date format. Please use the date picker."))

    old_date = order.delivery_date
    order.delivery_date = new_date

    # If order was AWAITING_DELIVERY_DATE, move to VALIDATED
    if order.status == "AWAITING_DELIVERY_DATE":
        order.status = "VALIDATED"

    token_rec.status = "UPDATED"

    audit = AuditLog(
        order_id=order.id,
        event_type="DELIVERY_DATE_CONFIRMED",
        description=f"Vendor confirmed delivery date: {old_date or 'none'} → {new_date} via portal (token {token[:8]}…)",
        performed_by="vendor_portal",
    )
    db.add(audit)
    db.commit()

    logger.info(f"Delivery date confirmed for {order.po_number}: {new_date}")
    return HTMLResponse(_portal_page(order, token, locked=False, success=True))


# ══════════════════════════════════════════════════════════════════════════
# HTML TEMPLATES
# ══════════════════════════════════════════════════════════════════════════

def _portal_page(order: OrderLedger, token: str, locked: bool, success: bool, error: str = "") -> str:
    delivery_display = order.delivery_date or ""
    cutoff_msg = ""
    if locked and order.delivery_date:
        try:
            delivery_dt = datetime.strptime(order.delivery_date, "%Y-%m-%d")
            cutoff_dt = delivery_dt - timedelta(hours=CUTOFF_HOURS)
            cutoff_msg = f"The 36-hour modification window closed on {cutoff_dt.strftime('%d %b %Y at %H:%M UTC')}."
        except Exception:
            cutoff_msg = "The modification window has closed."

    # Build line item rows
    line_rows = ""
    for item in order.line_items:
        if not item.is_valid:
            continue  # only show valid lines to vendor
        line_rows += f"""
          <tr>
            <td class="td-desc">{item.description or '—'}</td>
            <td class="td-center">{item.uom or '—'}</td>
            <td class="td-right">{int(item.qty) if item.qty else '—'}</td>
          </tr>"""

    if not line_rows:
        line_rows = '<tr><td colspan="3" class="td-empty">No line items</td></tr>'

    # Date input section
    if success:
        date_section = f"""
        <div class="success-box">
          <div class="success-icon">✓</div>
          <h2 class="success-title">Delivery Date Confirmed</h2>
          <p class="success-sub">Thank you. The confirmed delivery date is:</p>
          <p class="confirmed-date">{order.delivery_date}</p>
          <p class="success-note">Heritage Foods operations have been notified. No further action is required.</p>
        </div>"""
    elif locked:
        date_section = f"""
        <div class="locked-box">
          <div class="locked-icon">🔒</div>
          <h3 class="locked-title">Modification Window Closed</h3>
          <p class="locked-sub">{cutoff_msg}</p>
          <div class="date-display">{delivery_display or 'Date not set'}</div>
          <p class="locked-note">To make changes after the cutoff, please contact your Heritage Foods Key Account Manager directly.</p>
        </div>"""
    else:
        min_date = datetime.now().strftime("%Y-%m-%d")
        error_html = f'<p class="form-error">⚠ {error}</p>' if error else ""
        date_section = f"""
        {error_html}
        <form method="POST" action="/vendor/{token}/confirm" class="date-form">
          <label class="form-label">Confirm or update the delivery date</label>
          <input
            type="date"
            name="delivery_date"
            class="date-input"
            value="{delivery_display}"
            min="{min_date}"
            required
          />
          <p class="form-hint">
            Delivery date can be modified up to 36 hours before the scheduled date.
            After that, please contact your KAM.
          </p>
          <button type="submit" class="submit-btn">Confirm Delivery Date</button>
        </form>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <title>Delivery Confirmation — {order.po_number}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f0fdf4;
      color: #111827;
      min-height: 100vh;
      padding: 0;
    }}

    /* ── Header ── */
    .header {{
      background: linear-gradient(135deg, #1E6B3C, #2A8A4F);
      padding: 20px 20px 24px;
      text-align: center;
    }}
    .header-eyebrow {{
      font-size: 10px;
      color: rgba(255,255,255,0.7);
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .header-title {{
      font-size: 20px;
      font-weight: 700;
      color: #fff;
      line-height: 1.25;
    }}
    .header-po {{
      font-size: 12px;
      color: rgba(255,255,255,0.8);
      margin-top: 4px;
      font-family: 'Courier New', monospace;
    }}

    /* ── Main container ── */
    .container {{
      max-width: 520px;
      margin: 0 auto;
      padding: 20px 16px 40px;
    }}

    /* ── Order summary card ── */
    .card {{
      background: #fff;
      border: 1px solid #d1fae5;
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 16px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    }}
    .card-title {{
      font-size: 10px;
      font-weight: 700;
      color: #9ca3af;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-bottom: 12px;
    }}
    .meta-row {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      padding: 6px 0;
      border-bottom: 1px solid #f3f4f6;
      font-size: 13px;
    }}
    .meta-row:last-child {{ border-bottom: none; }}
    .meta-label {{ color: #6b7280; flex-shrink: 0; }}
    .meta-value {{ color: #111827; font-weight: 500; text-align: right; }}
    .meta-value.green {{ color: #1E6B3C; }}

    /* ── Line items table ── */
    .items-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .items-table thead tr {{
      background: #f9fafb;
      border-bottom: 1px solid #e5e7eb;
    }}
    .items-table th {{
      padding: 9px 10px;
      font-size: 10px;
      font-weight: 700;
      color: #9ca3af;
      text-transform: uppercase;
      letter-spacing: 0.07em;
    }}
    .td-desc {{ padding: 10px; color: #111827; }}
    .td-center {{ padding: 10px; text-align: center; color: #6b7280; }}
    .td-right {{ padding: 10px; text-align: right; font-weight: 600; color: #1E6B3C; font-family: monospace; }}
    .td-empty {{ padding: 20px; text-align: center; color: #9ca3af; font-style: italic; }}
    .items-table tbody tr {{ border-bottom: 1px solid #f3f4f6; }}
    .items-table tbody tr:last-child {{ border-bottom: none; }}

    /* ── Date form ── */
    .date-form {{
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .form-label {{
      font-size: 13px;
      font-weight: 600;
      color: #374151;
    }}
    .date-input {{
      width: 100%;
      padding: 14px 16px;
      font-size: 16px; /* 16px prevents iOS zoom */
      border: 2px solid #d1d5db;
      border-radius: 10px;
      background: #fff;
      color: #111827;
      outline: none;
      transition: border-color 0.15s;
      -webkit-appearance: none;
    }}
    .date-input:focus {{ border-color: #1E6B3C; box-shadow: 0 0 0 3px rgba(30,107,60,0.1); }}
    .form-hint {{
      font-size: 12px;
      color: #9ca3af;
      line-height: 1.5;
    }}
    .form-error {{
      font-size: 13px;
      color: #dc2626;
      background: #fef2f2;
      border: 1px solid #fecaca;
      border-radius: 8px;
      padding: 10px 14px;
    }}
    .submit-btn {{
      width: 100%;
      padding: 16px;
      background: #1E6B3C;
      color: #fff;
      font-size: 15px;
      font-weight: 700;
      border: none;
      border-radius: 10px;
      cursor: pointer;
      letter-spacing: 0.01em;
      box-shadow: 0 2px 8px rgba(30,107,60,0.3);
      transition: background 0.15s, transform 0.1s;
      -webkit-tap-highlight-color: transparent;
    }}
    .submit-btn:active {{ background: #155230; transform: scale(0.99); }}

    /* ── Success state ── */
    .success-box {{
      text-align: center;
      padding: 24px 16px;
    }}
    .success-icon {{
      width: 56px; height: 56px;
      background: #d1fae5;
      color: #1E6B3C;
      font-size: 26px;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 16px;
    }}
    .success-title {{
      font-size: 20px;
      font-weight: 700;
      color: #1E6B3C;
      margin-bottom: 8px;
    }}
    .success-sub {{
      font-size: 14px;
      color: #6b7280;
      margin-bottom: 10px;
    }}
    .confirmed-date {{
      font-size: 24px;
      font-weight: 700;
      color: #111827;
      margin-bottom: 16px;
      font-family: monospace;
    }}
    .success-note {{
      font-size: 12px;
      color: #9ca3af;
      line-height: 1.6;
    }}

    /* ── Locked state ── */
    .locked-box {{
      text-align: center;
      padding: 24px 16px;
    }}
    .locked-icon {{
      font-size: 36px;
      margin-bottom: 12px;
    }}
    .locked-title {{
      font-size: 17px;
      font-weight: 700;
      color: #b45309;
      margin-bottom: 8px;
    }}
    .locked-sub {{
      font-size: 13px;
      color: #6b7280;
      margin-bottom: 16px;
      line-height: 1.6;
    }}
    .date-display {{
      display: inline-block;
      padding: 10px 20px;
      background: #fef3c7;
      border: 1px solid #fde68a;
      border-radius: 8px;
      font-size: 18px;
      font-weight: 700;
      color: #92400e;
      font-family: monospace;
      margin-bottom: 16px;
    }}
    .locked-note {{
      font-size: 12px;
      color: #9ca3af;
      line-height: 1.6;
    }}

    /* ── Footer ── */
    .footer {{
      text-align: center;
      margin-top: 32px;
      font-size: 11px;
      color: #9ca3af;
      line-height: 1.7;
      padding: 0 16px;
    }}
    .footer-logo {{
      font-weight: 700;
      color: #1E6B3C;
      font-size: 12px;
    }}
  </style>
</head>
<body>

  <div class="header">
    <p class="header-eyebrow">Heritage Foods Limited</p>
    <h1 class="header-title">Delivery Confirmation</h1>
    <p class="header-po">{order.po_number}</p>
  </div>

  <div class="container">

    <!-- Order Summary -->
    <div class="card">
      <p class="card-title">Order Details</p>
      <div class="meta-row">
        <span class="meta-label">Customer</span>
        <span class="meta-value">{order.customer_name or order.customer_code or '—'}</span>
      </div>
      <div class="meta-row">
        <span class="meta-label">Ship-to Address</span>
        <span class="meta-value">{order.ship_to_address or '—'}</span>
      </div>
      <div class="meta-row">
        <span class="meta-label">Current Delivery Date</span>
        <span class="meta-value green">{order.delivery_date or 'Not set'}</span>
      </div>
    </div>

    <!-- Line Items -->
    <div class="card">
      <p class="card-title">Line Items</p>
      <table class="items-table">
        <thead>
          <tr>
            <th style="text-align:left;">Product</th>
            <th>UOM</th>
            <th style="text-align:right;">Qty</th>
          </tr>
        </thead>
        <tbody>{line_rows}</tbody>
      </table>
    </div>

    <!-- Date Confirmation Section -->
    <div class="card">
      <p class="card-title">{'Delivery Confirmed' if success else ('Date Locked' if locked else 'Confirm Delivery Date')}</p>
      {date_section}
    </div>

  </div>

  <div class="footer">
    <p class="footer-logo">Heritage Foods Limited</p>
    <p>PO Automation Platform · Secure Vendor Portal</p>
    <p>This link expires in {TOKEN_EXPIRY_DAYS} days from when it was sent.</p>
  </div>

</body>
</html>"""


def _error_page(title: str, message: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Heritage Foods</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; background: #f9fafb; display: flex;
            align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }}
    .box {{ background: #fff; border-radius: 12px; padding: 36px 28px; max-width: 400px;
            text-align: center; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
    .icon {{ font-size: 40px; margin-bottom: 16px; }}
    h1 {{ font-size: 20px; font-weight: 700; color: #111827; margin-bottom: 10px; }}
    p {{ font-size: 14px; color: #6b7280; line-height: 1.6; }}
    .brand {{ margin-top: 28px; font-size: 11px; color: #9ca3af; }}
  </style>
</head>
<body>
  <div class="box">
    <div class="icon">⚠️</div>
    <h1>{title}</h1>
    <p>{message}</p>
    <p class="brand">Heritage Foods Limited · PO Automation Platform</p>
  </div>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════════════════════════════════════

def _resolve_vendor_email(order: OrderLedger, db: Session) -> str | None:
    """Find the best vendor contact email for this order."""
    from app.models.models import CustomerMapping

    # 1. CustomerMapping contact email (most reliable)
    if order.site_code:
        rec = db.query(CustomerMapping).filter(
            CustomerMapping.site_code == order.site_code
        ).first()
        if rec and rec.email_id:
            return rec.email_id

    if order.sold_to_party:
        rec = db.query(CustomerMapping).filter(
            CustomerMapping.sold_to_party == order.sold_to_party
        ).first()
        if rec and rec.email_id:
            return rec.email_id

    # 2. Fallback: the email sender who sent the PO
    if order.email_sender and "@" in order.email_sender:
        return order.email_sender

    return None