from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class OrderLedger(Base):
    __tablename__ = "order_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    po_number = Column(String(50), nullable=False, index=True)
    po_date = Column(String(20))
    customer_code = Column(String(50), index=True)
    customer_name = Column(String(255))
    vendor_gstin = Column(String(50))
    is_update = Column(Boolean, default=False)
    ship_to_code = Column(String(50))
    ship_to_address = Column(Text)
    delivery_date = Column(String(20))
    expiry_date = Column(String(20))
    status = Column(String(50), default="NEW")
    total_value = Column(Float)
    email_uid = Column(String(50))
    email_subject = Column(String(500))
    email_sender = Column(String(255))
    drive_link = Column(String(500))
    raw_extraction_data = Column(JSON)
    rejection_summary = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    line_items = relationship("OrderLineItem", back_populates="order", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="order", cascade="all, delete-orphan")


class OrderLineItem(Base):
    __tablename__ = "order_line_item"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("order_ledger.id"), nullable=False)
    material_code = Column(String(50))
    description = Column(String(255))
    uom = Column(String(20))
    hsn_code = Column(String(20))
    qty = Column(Float)
    unit_price = Column(Float)
    mrp = Column(Float)
    tax_rate = Column(Float)
    tax_amount = Column(Float)
    line_total = Column(Float)
    is_valid = Column(Boolean, default=True)
    rejection_reason = Column(String(500))

    order = relationship("OrderLedger", back_populates="line_items")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("order_ledger.id"), nullable=False)
    event_type = Column(String(100))  # STATUS_CHANGE, LINE_EDIT, PUSH_SAP, etc.
    description = Column(Text)
    old_value = Column(Text)
    new_value = Column(Text)
    performed_by = Column(String(100), default="system")
    created_at = Column(DateTime, server_default=func.now())

    order = relationship("OrderLedger", back_populates="audit_logs")


# ── Master Data Tables ──────────────────────────────────────────────────────

class ProductMapping(Base):
    __tablename__ = "product_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_product_text = Column(String(500), nullable=False)
    sap_material_code = Column(String(50), nullable=False)
    sap_product_description = Column(String(255))
    customer_code = Column(String(50))
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PriceMaster(Base):
    __tablename__ = "price_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_code = Column(String(50), nullable=False)
    sap_material_code = Column(String(50), nullable=False)
    approved_price = Column(Float, nullable=False)
    effective_from = Column(String(20))
    effective_to = Column(String(20))
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LocationMapping(Base):
    __tablename__ = "location_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_code = Column(String(50), nullable=False)
    address_pattern = Column(String(500), nullable=False)
    sap_ship_to_code = Column(String(50), nullable=False)
    city = Column(String(100))
    state = Column(String(100))
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class InventoryMaster(Base):
    __tablename__ = "inventory_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sap_material_code = Column(String(50), nullable=False)
    plant_code = Column(String(20), nullable=False)
    unrestricted_stock = Column(Float, default=0)
    last_refreshed = Column(DateTime, server_default=func.now())


class CaseLotMaster(Base):
    __tablename__ = "case_lot_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sap_material_code = Column(String(50), nullable=False)
    sales_district = Column(String(50), nullable=False)
    case_qty = Column(Float, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DistrictMapping(Base):
    __tablename__ = "district_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ship_to_code = Column(String(50), nullable=False)
    sales_district = Column(String(50), nullable=False)
    customer_code = Column(String(50))
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CustomerMapping(Base):
    __tablename__ = "customer_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    variation_name = Column(String(255), nullable=False)
    normalized_code = Column(String(50), nullable=False)
    display_name = Column(String(255))
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DeliveryToken(Base):
    __tablename__ = "delivery_token"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(100), unique=True, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("order_ledger.id"), nullable=False)
    recipient_email = Column(String(255))
    status = Column(String(50), default="PENDING")  # PENDING, VISITED, UPDATED
    expires_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())


class SystemCheckpoint(Base):
    """Stores IMAP last-processed UID to prevent duplicate processing."""
    __tablename__ = "system_checkpoint"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(500))
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())