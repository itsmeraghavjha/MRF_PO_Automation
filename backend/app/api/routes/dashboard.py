from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import datetime, date

from app.db.base import get_db
from app.models.models import OrderLedger
from app.schemas.schemas import DashboardResponse, DashboardKPIs, StatusBreakdown

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

STATUS_META = {
    "NEW":                   {"label": "Processing",    "color": "#6366f1"},
    "VALIDATED":             {"label": "Ready for SAP", "color": "#10b981"},
    "VALIDATION_FAILED":     {"label": "Needs Review",  "color": "#ef4444"},
    "AWAITING_DELIVERY_DATE":{"label": "Awaiting Date", "color": "#f59e0b"},
    "SAP_SUCCESS":           {"label": "SAP Pushed",    "color": "#3b82f6"},
}


@router.get("", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    today = date.today()

    # Today's orders
    today_orders = db.query(OrderLedger).filter(
        func.date(OrderLedger.created_at) == today
    ).all()

    all_orders = db.query(OrderLedger).all()

    # KPIs
    total_today = len(today_orders)
    total_all = len(all_orders)
    value_today = sum(o.total_value or 0 for o in today_orders)
    value_all = sum(o.total_value or 0 for o in all_orders)

    auto_processed = sum(1 for o in all_orders if o.status == "SAP_SUCCESS")
    exceptions_pending = sum(1 for o in all_orders if o.status == "VALIDATION_FAILED")
    sap_pushed = auto_processed

    success_rate = (auto_processed / total_all * 100) if total_all > 0 else 0.0

    # Status breakdown
    status_counts = {}
    for order in all_orders:
        status_counts[order.status] = status_counts.get(order.status, 0) + 1

    breakdown = []
    for status, count in status_counts.items():
        meta = STATUS_META.get(status, {"label": status, "color": "#6b7280"})
        breakdown.append(StatusBreakdown(
            status=status,
            count=count,
            label=meta["label"],
            color=meta["color"]
        ))

    # Recent orders (last 10)
    from app.api.routes.orders import _to_summary
    from sqlalchemy import desc
    recent = db.query(OrderLedger).order_by(desc(OrderLedger.created_at)).limit(10).all()

    return DashboardResponse(
        kpis=DashboardKPIs(
            total_pos_today=total_today,
            total_pos_all_time=total_all,
            total_value_today=value_today,
            total_value_all_time=value_all,
            auto_processed=auto_processed,
            exceptions_pending=exceptions_pending,
            sap_pushed=sap_pushed,
            success_rate=round(success_rate, 1)
        ),
        status_breakdown=breakdown,
        recent_orders=[_to_summary(o) for o in recent]
    )