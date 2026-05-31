from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ── Order Schemas ──────────────────────────────────────────────────────────

class LineItemBase(BaseModel):
    material_code: Optional[str] = None
    customer_sku: Optional[str] = None
    description: Optional[str] = None
    uom: Optional[str] = None
    hsn_code: Optional[str] = None
    qty: Optional[float] = None
    unit_price: Optional[float] = None
    mrp: Optional[float] = None
    nlc: Optional[float] = None
    tax_rate: Optional[float] = None
    tax_amount: Optional[float] = None
    line_total: Optional[float] = None
    is_valid: bool = True
    rejection_reason: Optional[str] = None


class LineItemResponse(LineItemBase):
    id: int
    order_id: int

    class Config:
        from_attributes = True


class LineItemUpdate(BaseModel):
    material_code: Optional[str] = None
    qty: Optional[float] = None
    unit_price: Optional[float] = None


class AuditLogResponse(BaseModel):
    id: int
    event_type: str
    description: Optional[str]
    performed_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class OrderSummary(BaseModel):
    id: int
    po_number: str
    po_date: Optional[str]
    customer_code: Optional[str]
    customer_name: Optional[str]
    sold_to_party: Optional[str]
    status: str
    total_value: Optional[float]
    email_sender: Optional[str]
    rejection_summary: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    line_item_count: int = 0
    failed_line_count: int = 0

    class Config:
        from_attributes = True


class OrderDetail(OrderSummary):
    vendor_gstin: Optional[str]
    ship_to_code: Optional[str]
    ship_to_address: Optional[str]
    site_code: Optional[str]
    sales_district: Optional[str]
    sales_office: Optional[str]
    delivery_date: Optional[str]
    expiry_date: Optional[str]
    email_uid: Optional[str]
    email_subject: Optional[str]
    drive_link: Optional[str]
    is_update: bool
    line_items: List[LineItemResponse] = []
    audit_logs: List[AuditLogResponse] = []

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    orders: List[OrderSummary]
    total: int
    page: int
    page_size: int


# ── Dashboard Schemas ──────────────────────────────────────────────────────

class DashboardKPIs(BaseModel):
    total_pos_today: int
    total_pos_all_time: int
    total_value_today: float
    total_value_all_time: float
    auto_processed: int
    exceptions_pending: int
    sap_pushed: int
    success_rate: float


class StatusBreakdown(BaseModel):
    status: str
    count: int
    label: str
    color: str


class DashboardResponse(BaseModel):
    kpis: DashboardKPIs
    status_breakdown: List[StatusBreakdown]
    recent_orders: List[OrderSummary]


# ── Master Data Schemas ──────────────────────────────────────────────────────

# ── Customer Mapping ──

class CustomerMappingBase(BaseModel):
    cluster: str
    state: Optional[str] = None
    gst_number: Optional[str] = None
    full_address: Optional[str] = None
    site_code: Optional[str] = None
    sold_to_party: Optional[str] = None
    ship_to_party_code: Optional[str] = None
    sales_district: Optional[str] = None
    sales_office: Optional[str] = None
    person_responsible: Optional[str] = None
    email_id: Optional[str] = None
    contact_number: Optional[str] = None


class CustomerMappingResponse(CustomerMappingBase):
    id: int
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Product Mapping ──

class ProductMappingBase(BaseModel):
    sold_to_party: str
    customer_sku: Optional[str] = None
    customer_product_text: Optional[str] = None
    hfl_sku_code: str
    description: Optional[str] = None
    uom: Optional[str] = None
    division: Optional[str] = None
    taxable: bool = True


class ProductMappingResponse(ProductMappingBase):
    id: int
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Price Master ──

class PriceMasterBase(BaseModel):
    region: Optional[str] = None
    sales_district: str
    sold_to_party: str
    sku_code: str
    mrp: Optional[float] = None
    margin: Optional[float] = None
    offer: Optional[float] = None
    nlc: float                          # Net Landing Cost — the approved price
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None


class PriceMasterResponse(PriceMasterBase):
    id: int
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Location Mapping (fallback) ──

class LocationMappingBase(BaseModel):
    cluster: str
    address_pattern: str
    sap_ship_to_code: str
    sales_district: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None


class LocationMappingResponse(LocationMappingBase):
    id: int
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Inventory ──

class InventoryMasterBase(BaseModel):
    hfl_sku_code: str
    plant_code: str
    unrestricted_stock: float = 0


class InventoryMasterResponse(InventoryMasterBase):
    id: int
    last_refreshed: Optional[datetime]

    class Config:
        from_attributes = True


# ── Case Lot ──

class CaseLotMasterBase(BaseModel):
    cluster: str
    sales_district: str
    case_qty: float
    sku_code: str


class CaseLotMasterResponse(CaseLotMasterBase):
    id: int
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── SH-SKU-SO ──

class SHSKUSalesOfficeBase(BaseModel):
    sales_office: str
    ship_to_code: str
    hfl_sku_code: str
    material_description: Optional[str] = None


class SHSKUSalesOfficeResponse(SHSKUSalesOfficeBase):
    id: int
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Validation Schemas ──────────────────────────────────────────────────────

class ValidationResult(BaseModel):
    rule_id: str
    rule_name: str
    passed: bool
    failure_reason: Optional[str] = None
    affected_line_ids: List[int] = []


class RevalidateResponse(BaseModel):
    order_id: int
    all_passed: bool
    new_status: str
    validation_results: List[ValidationResult]


# ── SAP Schemas ──────────────────────────────────────────────────────────

class SAPPushResponse(BaseModel):
    order_id: int
    po_number: str
    csv_filename: str
    csv_path: str
    line_count: int
    pushed_at: datetime


# ── Import Response ──────────────────────────────────────────────────────

class ImportResponse(BaseModel):
    imported: int
    skipped: int = 0
    errors: List[str] = []
    message: str



class DistrictMappingBase(BaseModel):
    ship_to_code: str
    sales_district: str
    customer_code: Optional[str] = None
 
 
class DistrictMappingResponse(DistrictMappingBase):
    id: int
    updated_at: Optional[datetime]
 
    class Config:
        from_attributes = True