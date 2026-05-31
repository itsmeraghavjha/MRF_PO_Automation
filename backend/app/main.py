"""
Heritage Foods PO Automation Platform — Backend API
FastAPI application with APScheduler for background ingestion.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.config import settings
from app.db.base import init_db
from app.api.routes import orders, dashboard, master_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB and start background scheduler on startup."""
    logger.info("Starting Heritage Foods PO Automation Platform")

    # Initialize database tables
    init_db()
    logger.info("Database initialized")

    # Start email ingestion scheduler
    if settings.IMAP_USER:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from app.services.ingestion import run_ingestion_cycle

            scheduler = BackgroundScheduler()
            scheduler.add_job(
                run_ingestion_cycle,
                "interval",
                seconds=settings.IMAP_POLL_INTERVAL_SECONDS,
                id="email_ingestion",
                max_instances=1
            )
            scheduler.start()
            app.state.scheduler = scheduler
            logger.info(f"Email ingestion scheduler started (every {settings.IMAP_POLL_INTERVAL_SECONDS}s)")
        except Exception as e:
            logger.warning(f"Could not start email scheduler: {e}")
    else:
        logger.info("IMAP_USER not configured — email ingestion disabled")

    # Seed demo data if database is empty
    _seed_demo_data_if_empty()

    yield

    # Shutdown
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown()
        logger.info("Scheduler stopped")


app = FastAPI(
    title="Heritage Foods PO Automation API",
    description="Purchase Order Automation Platform — Heritage Foods Limited",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for stored PDFs
pdf_dir = Path(settings.PDF_STORAGE_DIR)
pdf_dir.mkdir(parents=True, exist_ok=True)
app.mount("/pdfs", StaticFiles(directory=str(pdf_dir)), name="pdfs")

# Routes
app.include_router(orders.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(master_data.router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Heritage Foods PO Automation"}


def _seed_demo_data_if_empty():
    """Seed realistic demo data for development/demo purposes."""
    from app.db.base import SessionLocal
    from app.models.models import (
        OrderLedger, OrderLineItem, ProductMapping,
        PriceMaster, LocationMapping, InventoryMaster,
        CaseLotMaster, DistrictMapping, CustomerMapping
    )
    from datetime import datetime, timedelta
    import random

    db = SessionLocal()
    try:
        if db.query(OrderLedger).count() > 0:
            return

        logger.info("Seeding demo data...")

        # Customer mappings
        customers = [
            CustomerMapping(variation_name="Reliance Retail", normalized_code="RRL", display_name="Reliance Retail Ltd"),
            CustomerMapping(variation_name="Reliance Smart", normalized_code="RRL", display_name="Reliance Retail Ltd"),
            CustomerMapping(variation_name="DMart", normalized_code="DMT", display_name="Avenue Supermarts"),
            CustomerMapping(variation_name="D-Mart", normalized_code="DMT", display_name="Avenue Supermarts"),
            CustomerMapping(variation_name="BigBasket", normalized_code="BBK", display_name="BigBasket"),
            CustomerMapping(variation_name="Zepto", normalized_code="ZEP", display_name="Zepto"),
            CustomerMapping(variation_name="Amazon", normalized_code="AMZ", display_name="Amazon India"),
            CustomerMapping(variation_name="Walmart", normalized_code="WMT", display_name="Walmart India"),
        ]
        db.bulk_save_objects(customers)

        # Products
        products = [
            ProductMapping(customer_product_text="Heritage Fresh Milk 1L", sap_material_code="HF-MIL-001", sap_product_description="Heritage Fresh Milk 1L", customer_code="RRL"),
            ProductMapping(customer_product_text="Heritage Curd 400g", sap_material_code="HF-CUR-400", sap_product_description="Heritage Curd 400g", customer_code="RRL"),
            ProductMapping(customer_product_text="Heritage Butter 500g", sap_material_code="HF-BUT-500", sap_product_description="Heritage Butter 500g", customer_code="RRL"),
            ProductMapping(customer_product_text="Heritage Paneer 200g", sap_material_code="HF-PAN-200", sap_product_description="Heritage Paneer 200g", customer_code="DMT"),
            ProductMapping(customer_product_text="Heritage Ghee 1kg", sap_material_code="HF-GHE-001", sap_product_description="Heritage Pure Ghee 1kg", customer_code="DMT"),
            ProductMapping(customer_product_text="Heritage Lassi 200ml", sap_material_code="HF-LAS-200", sap_product_description="Heritage Lassi 200ml", customer_code="BBK"),
            ProductMapping(customer_product_text="Heritage Cheese Slice 200g", sap_material_code="HF-CHE-200", sap_product_description="Heritage Processed Cheese 200g", customer_code="ZEP"),
        ]
        db.bulk_save_objects(products)

        # Prices
        prices = [
            PriceMaster(customer_code="RRL", sap_material_code="HF-MIL-001", approved_price=62.00),
            PriceMaster(customer_code="RRL", sap_material_code="HF-CUR-400", approved_price=45.00),
            PriceMaster(customer_code="RRL", sap_material_code="HF-BUT-500", approved_price=280.00),
            PriceMaster(customer_code="DMT", sap_material_code="HF-PAN-200", approved_price=85.00),
            PriceMaster(customer_code="DMT", sap_material_code="HF-GHE-001", approved_price=650.00),
            PriceMaster(customer_code="BBK", sap_material_code="HF-LAS-200", approved_price=28.00),
            PriceMaster(customer_code="ZEP", sap_material_code="HF-CHE-200", approved_price=115.00),
        ]
        db.bulk_save_objects(prices)

        # Inventory
        inventory = [
            InventoryMaster(sap_material_code="HF-MIL-001", plant_code="HYD1", unrestricted_stock=5000),
            InventoryMaster(sap_material_code="HF-CUR-400", plant_code="HYD1", unrestricted_stock=2400),
            InventoryMaster(sap_material_code="HF-BUT-500", plant_code="HYD1", unrestricted_stock=800),
            InventoryMaster(sap_material_code="HF-PAN-200", plant_code="HYD1", unrestricted_stock=1200),
            InventoryMaster(sap_material_code="HF-GHE-001", plant_code="HYD1", unrestricted_stock=450),
            InventoryMaster(sap_material_code="HF-LAS-200", plant_code="HYD1", unrestricted_stock=3000),
            InventoryMaster(sap_material_code="HF-CHE-200", plant_code="HYD1", unrestricted_stock=600),
        ]
        db.bulk_save_objects(inventory)

        db.flush()

        # Demo Orders
        demo_orders = [
            {
                "po_number": "RRL-PO-2026-4521",
                "customer_code": "RRL", "customer_name": "Reliance Retail Ltd",
                "status": "SAP_SUCCESS", "total_value": 186000,
                "po_date": "2026-05-29", "delivery_date": "2026-06-02",
                "vendor_gstin": "36AAACH1234F1ZR",
                "ship_to_code": "RRL-HYD-01", "ship_to_address": "Reliance Smart, Jubilee Hills, Hyderabad",
                "email_sender": "procurement@relianceretail.com",
            },
            {
                "po_number": "DMT-PO-2026-8834",
                "customer_code": "DMT", "customer_name": "Avenue Supermarts (DMart)",
                "status": "VALIDATION_FAILED", "total_value": 142500,
                "po_date": "2026-05-30", "delivery_date": "2026-06-03",
                "vendor_gstin": "36AAACH1234F1ZR",
                "ship_to_code": None, "ship_to_address": "DMart, Kukatpally, Hyderabad",
                "email_sender": "po@dmart.in",
                "rejection_summary": "VR-02: 2 price mismatch(es) | VR-05: Unknown Location",
            },
            {
                "po_number": "BBK-PO-2026-3301",
                "customer_code": "BBK", "customer_name": "BigBasket",
                "status": "VALIDATED", "total_value": 84000,
                "po_date": "2026-05-30", "delivery_date": "2026-06-01",
                "vendor_gstin": "36AAACH1234F1ZR",
                "ship_to_code": "BBK-HYD-02", "ship_to_address": "BigBasket Warehouse, Gachibowli, Hyderabad",
                "email_sender": "supply@bigbasket.com",
            },
            {
                "po_number": "ZEP-PO-2026-1102",
                "customer_code": "ZEP", "customer_name": "Zepto",
                "status": "AWAITING_DELIVERY_DATE", "total_value": 57600,
                "po_date": "2026-05-31", "delivery_date": None,
                "vendor_gstin": "36AAACH1234F1ZR",
                "ship_to_code": "ZEP-HYD-01", "ship_to_address": "Zepto Dark Store, Madhapur, Hyderabad",
                "email_sender": "ops@zepto.com",
            },
            {
                "po_number": "RRL-PO-2026-4498",
                "customer_code": "RRL", "customer_name": "Reliance Retail Ltd",
                "status": "SAP_SUCCESS", "total_value": 224000,
                "po_date": "2026-05-28", "delivery_date": "2026-05-31",
                "vendor_gstin": "36AAACH1234F1ZR",
                "ship_to_code": "RRL-HYD-01", "ship_to_address": "Reliance Fresh, Banjara Hills, Hyderabad",
                "email_sender": "procurement@relianceretail.com",
            },
            {
                "po_number": "AMZ-PO-2026-9920",
                "customer_code": "AMZ", "customer_name": "Amazon India",
                "status": "VALIDATION_FAILED", "total_value": 98750,
                "po_date": "2026-05-31", "delivery_date": "2026-06-04",
                "vendor_gstin": None,
                "ship_to_code": "AMZ-HYD-FC", "ship_to_address": "Amazon FC, Outer Ring Road, Hyderabad",
                "email_sender": "vendor-orders@amazon.in",
                "rejection_summary": "VR-06: Missing GSTIN on PO",
            },
            {
                "po_number": "DMT-PO-2026-8801",
                "customer_code": "DMT", "customer_name": "Avenue Supermarts (DMart)",
                "status": "SAP_SUCCESS", "total_value": 312000,
                "po_date": "2026-05-27", "delivery_date": "2026-05-30",
                "vendor_gstin": "36AAACH1234F1ZR",
                "ship_to_code": "DMT-HYD-01", "ship_to_address": "DMart, SR Nagar, Hyderabad",
                "email_sender": "po@dmart.in",
            },
        ]

        for i, od in enumerate(demo_orders):
            order = OrderLedger(
                **{k: v for k, v in od.items() if k != "line_items"},
                created_at=datetime.now() - timedelta(hours=random.randint(1, 48)),
                raw_extraction_data={"demo": True}
            )
            db.add(order)
            db.flush()

            # Add line items
            items_data = [
                ("HF-MIL-001", "Heritage Fresh Milk 1L", "CS", 100, 62.00, 5),
                ("HF-CUR-400", "Heritage Curd 400g", "CS", 60, 45.00, 12),
                ("HF-BUT-500", "Heritage Butter 500g", "EA", 40, 280.00, 5),
            ]
            for mat, desc, uom, qty, price, tax in items_data:
                is_valid = od["status"] != "VALIDATION_FAILED"
                rejection = None
                if not is_valid and mat == "HF-BUT-500":
                    rejection = "Price Mismatch: PO ₹295.00 vs Master ₹280.00"
                    is_valid = False

                item = OrderLineItem(
                    order_id=order.id,
                    material_code=mat,
                    description=desc,
                    uom=uom,
                    qty=qty,
                    unit_price=price if is_valid else price + 15,
                    mrp=price * 1.2,
                    tax_rate=tax,
                    tax_amount=qty * price * tax / 100,
                    line_total=qty * price,
                    is_valid=is_valid,
                    rejection_reason=rejection
                )
                db.add(item)

        db.commit()
        logger.info("Demo data seeded successfully")

    except Exception as e:
        logger.error(f"Demo data seeding failed: {e}")
        db.rollback()
    finally:
        db.close()