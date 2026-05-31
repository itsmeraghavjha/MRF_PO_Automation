from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime, date

from app.db.base import get_db
from app.models.models import OrderLedger, OrderLineItem, AuditLog
from app.schemas.schemas import (
    OrderDetail, OrderSummary, OrderListResponse,
    LineItemUpdate, RevalidateResponse, SAPPushResponse, ValidationResult
)
from app.services.validation import run_validation
from app.services.sap_generator import generate_sap_csv

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=OrderListResponse)
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    customer_code: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(OrderLedger)

    if status:
        query = query.filter(OrderLedger.status == status)
    if customer_code:
        query = query.filter(OrderLedger.customer_code == customer_code)
    if search:
        query = query.filter(
            OrderLedger.po_number.contains(search) |
            OrderLedger.customer_name.contains(search) |
            OrderLedger.customer_code.contains(search)
        )

    total = query.count()
    orders = query.order_by(desc(OrderLedger.created_at)).offset((page - 1) * page_size).limit(page_size).all()

    return OrderListResponse(
        orders=[_to_summary(o) for o in orders],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(OrderLedger).filter(OrderLedger.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _to_detail(order)


@router.patch("/{order_id}/line-items/{item_id}")
def update_line_item(
    order_id: int,
    item_id: int,
    update: LineItemUpdate,
    performed_by: str = "ops_user",
    db: Session = Depends(get_db)
):
    order = db.query(OrderLedger).filter(OrderLedger.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    item = db.query(OrderLineItem).filter(
        OrderLineItem.id == item_id,
        OrderLineItem.order_id == order_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found")

    changes = []
    if update.material_code is not None:
        changes.append(f"material_code: {item.material_code} → {update.material_code}")
        item.material_code = update.material_code
    if update.qty is not None:
        changes.append(f"qty: {item.qty} → {update.qty}")
        item.qty = update.qty
        item.line_total = (item.qty or 0) * (item.unit_price or 0)
    if update.unit_price is not None:
        changes.append(f"unit_price: {item.unit_price} → {update.unit_price}")
        item.unit_price = update.unit_price
        item.line_total = (item.qty or 0) * (item.unit_price or 0)

    # Recalculate order total
    order.total_value = sum(
        (li.line_total or 0) for li in order.line_items
    )

    # Audit
    audit = AuditLog(
        order_id=order_id,
        event_type="LINE_EDIT",
        description=f"Item {item_id}: {'; '.join(changes)}",
        performed_by=performed_by
    )
    db.add(audit)
    db.commit()

    return {"success": True, "item_id": item_id, "changes": changes}


@router.post("/{order_id}/revalidate", response_model=RevalidateResponse)
def revalidate_order(
    order_id: int,
    performed_by: str = "ops_user",
    db: Session = Depends(get_db)
):
    order = db.query(OrderLedger).filter(OrderLedger.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    all_passed, summary = run_validation(order, db)

    new_status = "VALIDATED" if all_passed else "VALIDATION_FAILED"
    order.status = new_status

    audit = AuditLog(
        order_id=order_id,
        event_type="REVALIDATED",
        description=f"Re-validation → {new_status}. {summary}",
        performed_by=performed_by
    )
    db.add(audit)
    db.commit()

    return RevalidateResponse(
        order_id=order_id,
        all_passed=all_passed,
        new_status=new_status,
        validation_results=[]
    )


@router.post("/{order_id}/push-sap", response_model=SAPPushResponse)
def push_to_sap(
    order_id: int,
    performed_by: str = "ops_user",
    db: Session = Depends(get_db)
):
    order = db.query(OrderLedger).filter(OrderLedger.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != "VALIDATED":
        raise HTTPException(
            status_code=400,
            detail=f"Order must be VALIDATED before SAP push. Current status: {order.status}"
        )

    filename, filepath = generate_sap_csv(order)

    order.status = "SAP_SUCCESS"
    audit = AuditLog(
        order_id=order_id,
        event_type="SAP_PUSHED",
        description=f"SAP CSV generated: {filename}",
        performed_by=performed_by
    )
    db.add(audit)
    db.commit()

    return SAPPushResponse(
        order_id=order_id,
        po_number=order.po_number,
        csv_filename=filename,
        csv_path=filepath,
        line_count=len(order.line_items),
        pushed_at=datetime.now()
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_summary(order: OrderLedger) -> OrderSummary:
    failed_count = sum(1 for li in order.line_items if not li.is_valid)
    return OrderSummary(
        id=order.id,
        po_number=order.po_number,
        po_date=order.po_date,
        customer_code=order.customer_code,
        customer_name=order.customer_name,
        sold_to_party=order.sold_to_party,  # <--- ADD THIS LINE
        status=order.status,
        total_value=order.total_value,
        email_sender=order.email_sender,
        rejection_summary=order.rejection_summary,
        created_at=order.created_at or datetime.now(),
        updated_at=order.updated_at,
        line_item_count=len(order.line_items),
        failed_line_count=failed_count
    )


def _to_detail(order: OrderLedger) -> OrderDetail:
    summary = _to_summary(order)
    return OrderDetail(
        **summary.model_dump(),
        vendor_gstin=order.vendor_gstin,
        ship_to_code=order.ship_to_code,
        ship_to_address=order.ship_to_address,
        site_code=getattr(order, "site_code", None),             # <-- ADDED
        sales_district=getattr(order, "sales_district", None),   # <-- ADDED
        sales_office=getattr(order, "sales_office", None),       # <-- ADDED
        delivery_date=order.delivery_date,
        expiry_date=order.expiry_date,
        email_uid=order.email_uid,
        email_subject=order.email_subject,
        drive_link=order.drive_link,
        is_update=order.is_update or False,
        line_items=order.line_items,
        audit_logs=sorted(order.audit_logs, key=lambda x: x.created_at or datetime.min, reverse=True)
    )