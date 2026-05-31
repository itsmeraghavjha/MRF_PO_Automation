"""
Email Notification Service — Gmail SMTP.
Used for:
  1. Vendor delivery confirmation requests (Phase 3)
  2. Future: KAM exception alerts (Phase 2)
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """
    Send an email via Gmail SMTP.
    Returns True on success, False on failure (never raises).
    """
    if not settings.IMAP_USER or not settings.IMAP_PASSWORD:
        logger.warning(f"[EMAIL] SMTP not configured — would have sent to {to}: {subject}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.IMAP_USER
        msg["To"] = to

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
            smtp.sendmail(settings.IMAP_USER, to, msg.as_string())

        logger.info(f"[EMAIL] Sent to {to}: {subject}")
        return True

    except Exception as e:
        logger.error(f"[EMAIL] Failed to send to {to}: {e}")
        return False


def send_delivery_confirmation_request(
    to_email: str,
    po_number: str,
    customer_name: str,
    ship_to_address: str,
    delivery_date: str | None,
    line_items: list,
    token: str,
    base_url: str,
) -> bool:
    """Send vendor delivery confirmation email with tokenised portal link."""
    portal_url = f"{base_url}/vendor/{token}"

    delivery_display = delivery_date or "Not specified"

    # Build line items rows
    rows_html = ""
    for item in line_items:
        rows_html += f"""
        <tr style="border-bottom:1px solid #e5e7eb;">
          <td style="padding:10px 12px;font-size:13px;color:#111;">{item.get('description','—')}</td>
          <td style="padding:10px 12px;font-size:13px;color:#444;text-align:center;">{item.get('uom','—')}</td>
          <td style="padding:10px 12px;font-size:13px;font-weight:600;text-align:right;color:#1E6B3C;">{item.get('qty','—')}</td>
        </tr>"""

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#1E6B3C,#2A8A4F);padding:28px 32px;">
            <p style="margin:0;font-size:11px;color:rgba(255,255,255,0.7);letter-spacing:0.1em;text-transform:uppercase;">Heritage Foods Limited</p>
            <h1 style="margin:6px 0 0;font-size:22px;font-weight:700;color:#fff;">Delivery Confirmation Required</h1>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:28px 32px;">
            <p style="margin:0 0 20px;font-size:14px;color:#374151;line-height:1.6;">
              Dear Vendor Partner,<br><br>
              Purchase Order <strong style="color:#1E6B3C;">{po_number}</strong> from <strong>{customer_name}</strong> has been validated and is ready for dispatch planning.
              Please confirm or update the delivery date using the secure link below.
            </p>

            <!-- Order Summary Box -->
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;margin-bottom:24px;">
              <tr>
                <td style="padding:16px 20px;">
                  <p style="margin:0 0 6px;font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:0.08em;">Order Details</p>
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="padding:4px 0;font-size:13px;color:#6b7280;width:140px;">PO Number</td>
                      <td style="padding:4px 0;font-size:13px;font-weight:600;color:#111;font-family:monospace;">{po_number}</td>
                    </tr>
                    <tr>
                      <td style="padding:4px 0;font-size:13px;color:#6b7280;">Ship-to Address</td>
                      <td style="padding:4px 0;font-size:13px;color:#111;">{ship_to_address or '—'}</td>
                    </tr>
                    <tr>
                      <td style="padding:4px 0;font-size:13px;color:#6b7280;">Requested Delivery</td>
                      <td style="padding:4px 0;font-size:13px;font-weight:600;color:#1E6B3C;">{delivery_display}</td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>

            <!-- Line Items -->
            <p style="margin:0 0 10px;font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:0.08em;">Line Items</p>
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;margin-bottom:28px;">
              <thead>
                <tr style="background:#f3f4f6;">
                  <th style="padding:10px 12px;font-size:11px;font-weight:700;color:#6b7280;text-align:left;text-transform:uppercase;letter-spacing:0.06em;">Product</th>
                  <th style="padding:10px 12px;font-size:11px;font-weight:700;color:#6b7280;text-align:center;text-transform:uppercase;letter-spacing:0.06em;">UOM</th>
                  <th style="padding:10px 12px;font-size:11px;font-weight:700;color:#6b7280;text-align:right;text-transform:uppercase;letter-spacing:0.06em;">Qty</th>
                </tr>
              </thead>
              <tbody>{rows_html}</tbody>
            </table>

            <!-- CTA Button -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
              <tr>
                <td align="center">
                  <a href="{portal_url}"
                     style="display:inline-block;background:#1E6B3C;color:#fff;font-size:15px;font-weight:700;
                            text-decoration:none;padding:14px 36px;border-radius:8px;
                            box-shadow:0 2px 8px rgba(30,107,60,0.3);">
                    ✓ Confirm / Update Delivery Date
                  </a>
                </td>
              </tr>
            </table>

            <p style="margin:0;font-size:12px;color:#9ca3af;text-align:center;line-height:1.5;">
              This link is valid for 7 days and does not require a login.<br>
              If you did not expect this email, please contact Heritage Foods operations.
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f9fafb;padding:16px 32px;border-top:1px solid #e5e7eb;">
            <p style="margin:0;font-size:11px;color:#9ca3af;text-align:center;">
              Heritage Foods Limited · PO Automation Platform · This is an automated message
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    text = f"""Heritage Foods — Delivery Confirmation Required

PO Number: {po_number}
Customer: {customer_name}
Ship-to: {ship_to_address or '—'}
Requested Delivery Date: {delivery_display}

Please confirm or update the delivery date using this secure link:
{portal_url}

This link is valid for 7 days and does not require a login.
"""

    return send_email(to_email, f"[Action Required] Delivery Confirmation — {po_number}", html, text)