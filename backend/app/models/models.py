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
    customer_code = Column(String(50), index=True)   # Cluster / normalised code (e.g. RRL)
    customer_name = Column(String(255))
    sold_to_party = Column(String(20), index=True)   # SAP Sold-to party (e.g. 250029)
    vendor_gstin = Column(String(50))
    is_update = Column(Boolean, default=False)
    ship_to_code = Column(String(50))                # SAP Ship-to party code (e.g. 273774)
    ship_to_address = Column(Text)
    site_code = Column(String(50))                   # Vendor loc code as on PO (e.g. 2999)
    sales_district = Column(String(100))             # Resolved sales district (e.g. APBB01-Bobbili)
    sales_office = Column(String(100))               # SAP Sales office
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
    material_code = Column(String(50))        # HFL SKU CODE (e.g. 10017)
    customer_sku = Column(String(100))        # Customer's own SKU code (e.g. 590000720)
    description = Column(String(255))
    uom = Column(String(20))
    hsn_code = Column(String(20))
    qty = Column(Float)
    unit_price = Column(Float)
    mrp = Column(Float)
    nlc = Column(Float)                       # Net Landing Cost (approved price from price master)
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
    event_type = Column(String(100))
    description = Column(Text)
    old_value = Column(Text)
    new_value = Column(Text)
    performed_by = Column(String(100), default="system")
    created_at = Column(DateTime, server_default=func.now())

    order = relationship("OrderLedger", back_populates="audit_logs")


# ── Master Data Tables ──────────────────────────────────────────────────────

class CustomerMapping(Base):
    """
    Maps a customer's PO address / site code to SAP codes.
    One row per physical ship-to location per customer cluster.
    """
    __tablename__ = "customer_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Identification
    cluster = Column(String(50), nullable=False, index=True)   # RRL, DMT, BBK etc.
    state = Column(String(100))
    # GST
    gst_number = Column(String(20))                            # Customer's GST on PO
    # Address & Site
    full_address = Column(Text)                                # Full address as printed on PO
    site_code = Column(String(50), index=True)                 # Vendor loc / site code on PO (e.g. 2999)
    # SAP Codes
    sold_to_party = Column(String(20), index=True)             # SAP Sold-to party (e.g. 250029)
    ship_to_party_code = Column(String(20), index=True)        # SAP Ship-to party (e.g. 273774)
    sales_district = Column(String(100))                       # e.g. APBB01-Bobbili
    sales_office = Column(String(100))                         # e.g. 1961-Bobbili Sales Office
    # Contact
    person_responsible = Column(String(255))
    email_id = Column(String(255))
    contact_number = Column(String(50))
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ProductMapping(Base):
    """
    Maps a customer's SKU (description or code) to HFL's SAP material code.
    Keyed by sold_to_party + customer_sku.
    """
    __tablename__ = "product_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sold_to_party = Column(String(20), nullable=False, index=True)  # SAP sold-to (e.g. 250001)
    customer_sku = Column(String(100))                               # Customer's article code on PO
    customer_product_text = Column(String(500))                      # Customer's product description
    hfl_sku_code = Column(String(50), nullable=False)                # HFL SAP material code (e.g. 10017)
    description = Column(String(255))                                # HFL product description
    uom = Column(String(20))
    division = Column(String(100))
    taxable = Column(Boolean, default=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PriceMaster(Base):
    """
    Net Landing Cost (NLC) per Sold-to Party + Sales District + SKU.
    NLC is the approved price used for VR-02 validation.
    """
    __tablename__ = "price_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region = Column(String(100))
    sales_district = Column(String(100), nullable=False, index=True)  # e.g. APBB01-Bobbili
    sold_to_party = Column(String(20), nullable=False, index=True)     # e.g. 250029
    sku_code = Column(String(50), nullable=False, index=True)          # HFL SKU code (e.g. 70004)
    mrp = Column(Float)
    margin = Column(Float)
    offer = Column(Float)
    nlc = Column(Float, nullable=False)           # Net Landing Cost — used for price validation
    effective_from = Column(String(20))
    effective_to = Column(String(20))
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LocationMapping(Base):
    """
    Fallback address-pattern → SAP ship-to mapping.
    Primary lookup is CustomerMapping.site_code / full_address.
    This is kept for edge cases where address pattern matching is needed.
    """
    __tablename__ = "location_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster = Column(String(50), nullable=False)        # Customer cluster (was customer_code)
    address_pattern = Column(String(500), nullable=False)
    sap_ship_to_code = Column(String(50), nullable=False)
    sales_district = Column(String(100))
    city = Column(String(100))
    state = Column(String(100))
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class InventoryMaster(Base):
    __tablename__ = "inventory_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hfl_sku_code = Column(String(50), nullable=False, index=True)  # HFL material code
    plant_code = Column(String(20), nullable=False)
    unrestricted_stock = Column(Float, default=0)
    last_refreshed = Column(DateTime, server_default=func.now())


class CaseLotMaster(Base):
    """
    Minimum case lot multiples per cluster + sales district + SKU.
    """
    __tablename__ = "case_lot_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster = Column(String(50), nullable=False, index=True)        # e.g. RRL
    sales_district = Column(String(100), nullable=False, index=True) # e.g. APBB01-Bobbili
    case_qty = Column(Float, nullable=False)
    sku_code = Column(String(50), nullable=False)                    # HFL SKU code
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DistrictMapping(Base):
    """
    Maps SAP ship-to code → sales district (used in case lot resolution).
    Now can also be derived from CustomerMapping but kept for direct lookup.
    """
    __tablename__ = "district_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ship_to_code = Column(String(50), nullable=False, index=True)
    sales_district = Column(String(100), nullable=False)
    cluster = Column(String(50))   # was customer_code
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SHSKUSalesOffice(Base):
    """
    Valid combinations of Sales Office + Ship-to + SKU (SH-SKU-SO sheet).
    Used to validate that a given SKU is serviced from a given ship-to.
    """
    __tablename__ = "sh_sku_sales_office"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sales_office = Column(String(100), nullable=False, index=True)
    ship_to_code = Column(String(20), nullable=False, index=True)
    hfl_sku_code = Column(String(50), nullable=False, index=True)
    material_description = Column(String(255))
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DeliveryToken(Base):
    __tablename__ = "delivery_token"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(100), unique=True, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("order_ledger.id"), nullable=False)
    recipient_email = Column(String(255))
    status = Column(String(50), default="PENDING")
    expires_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())


class SystemCheckpoint(Base):
    __tablename__ = "system_checkpoint"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(500))
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())