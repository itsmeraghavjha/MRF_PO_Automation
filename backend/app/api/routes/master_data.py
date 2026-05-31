"""
Master Data API routes.
Supports CRUD + bulk Excel/CSV import for all mapping tables.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
import io
import logging

from app.db.base import get_db
from app.models.models import (
    ProductMapping, PriceMaster, LocationMapping,
    InventoryMaster, CaseLotMaster, DistrictMapping,
    CustomerMapping, SHSKUSalesOffice
)
from app.schemas.schemas import (
    ProductMappingBase, ProductMappingResponse,
    PriceMasterBase, PriceMasterResponse,
    LocationMappingBase, LocationMappingResponse,
    InventoryMasterBase, InventoryMasterResponse,
    CaseLotMasterBase, CaseLotMasterResponse,
    CustomerMappingBase, CustomerMappingResponse,
    SHSKUSalesOfficeBase, SHSKUSalesOfficeResponse,
    ImportResponse,
)

router = APIRouter(prefix="/master-data", tags=["master-data"])
logger = logging.getLogger(__name__)


def _read_upload(file: UploadFile, content: bytes) -> pd.DataFrame:
    """Parse CSV or Excel upload into a DataFrame."""
    if file.filename.endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))
    return pd.read_excel(io.BytesIO(content))


def _str(val) -> str:
    """Safe string conversion — turns NaN / None into empty string."""
    if pd.isna(val):
        return ""
    return str(val).strip()


def _float(val) -> float | None:
    try:
        if pd.isna(val):
            return None
        return float(val)
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOMER MAPPING
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/customers", response_model=List[CustomerMappingResponse])
def list_customers(db: Session = Depends(get_db)):
    return db.query(CustomerMapping).all()


@router.post("/customers", response_model=CustomerMappingResponse)
def create_customer(data: CustomerMappingBase, db: Session = Depends(get_db)):
    rec = CustomerMapping(**data.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.put("/customers/{id}", response_model=CustomerMappingResponse)
def update_customer(id: int, data: CustomerMappingBase, db: Session = Depends(get_db)):
    rec = db.query(CustomerMapping).filter(CustomerMapping.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in data.model_dump().items():
        setattr(rec, k, v)
    db.commit()
    db.refresh(rec)
    return rec


@router.delete("/customers/{id}")
def delete_customer(id: int, db: Session = Depends(get_db)):
    rec = db.query(CustomerMapping).filter(CustomerMapping.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(rec)
    db.commit()
    return {"deleted": id}


@router.post("/customers/import", response_model=ImportResponse)
async def import_customers(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Bulk import from the 'Customer Mapping' sheet.
    Expected columns (case-insensitive):
      State, Cluster, GST Number, Full Address as per PO,
      Site code/Vendor loc unique code(As mentioned in PO),
      Sales District, Sold to party code, Ship to Party Code,
      Sales office, Person Responsible, Email Id, Contact Number
    """
    content = await file.read()
    try:
        df = _read_upload(file, content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot parse file: {e}")

    # Normalise column names
    df.columns = [c.strip() for c in df.columns]

    records = []
    errors = []
    for i, row in df.iterrows():
        try:
            cluster = _str(row.get("Cluster", ""))
            if not cluster:
                errors.append(f"Row {i+2}: missing Cluster — skipped")
                continue
            records.append(CustomerMapping(
                cluster=cluster,
                state=_str(row.get("State", "")),
                gst_number=_str(row.get("GST Number", "")),
                full_address=_str(row.get("Full Address as per PO", "")),
                site_code=_str(row.get("Site code/Vendor loc unique code(As mentioned in PO)", "")),
                sales_district=_str(row.get("Sales District", "")),
                sold_to_party=_str(row.get("Sold to party code", "")),
                ship_to_party_code=_str(row.get("Ship to Party Code", "")),
                sales_office=_str(row.get("Sales office", "")),
                person_responsible=_str(row.get("Person Responsible", "")),
                email_id=_str(row.get("Email Id", "")),
                contact_number=_str(row.get("Contact Number", "")),
            ))
        except Exception as e:
            errors.append(f"Row {i+2}: {e}")

    db.query(CustomerMapping).delete()
    db.bulk_save_objects(records)
    db.commit()
    return ImportResponse(
        imported=len(records), skipped=len(errors), errors=errors,
        message=f"Customer mapping refreshed: {len(records)} records loaded."
    )


# ══════════════════════════════════════════════════════════════════════════════
# PRODUCT MAPPING (SKU Mapping)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/products", response_model=List[ProductMappingResponse])
def list_products(db: Session = Depends(get_db)):
    return db.query(ProductMapping).all()


@router.post("/products", response_model=ProductMappingResponse)
def create_product(data: ProductMappingBase, db: Session = Depends(get_db)):
    rec = ProductMapping(**data.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.put("/products/{id}", response_model=ProductMappingResponse)
def update_product(id: int, data: ProductMappingBase, db: Session = Depends(get_db)):
    rec = db.query(ProductMapping).filter(ProductMapping.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in data.model_dump().items():
        setattr(rec, k, v)
    db.commit()
    db.refresh(rec)
    return rec


@router.delete("/products/{id}")
def delete_product(id: int, db: Session = Depends(get_db)):
    rec = db.query(ProductMapping).filter(ProductMapping.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(rec)
    db.commit()
    return {"deleted": id}


@router.post("/products/import", response_model=ImportResponse)
async def import_products(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Bulk import from the 'SKU Mapping' sheet.
    Expected columns:
      Sold to Party, Customer SKU, Customer SKU Description,
      HFL SKU CODE, Description, UOM, Division, Taxable or Non Taxable
    """
    content = await file.read()
    try:
        df = _read_upload(file, content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot parse file: {e}")

    df.columns = [c.strip() for c in df.columns]

    records = []
    errors = []
    for i, row in df.iterrows():
        try:
            sold_to = _str(row.get("Sold to Party", ""))
            hfl_code = _str(row.get("HFL SKU CODE", ""))
            if not sold_to or not hfl_code:
                errors.append(f"Row {i+2}: missing Sold to Party or HFL SKU CODE — skipped")
                continue
            taxable_val = _str(row.get("Taxable or Non Taxable", "Taxable"))
            taxable = "non" not in taxable_val.lower()
            records.append(ProductMapping(
                sold_to_party=sold_to,
                customer_sku=_str(row.get("Customer SKU", "")),
                customer_product_text=_str(row.get("Customer SKU Description", "")),
                hfl_sku_code=hfl_code,
                description=_str(row.get("Description", "")),
                uom=_str(row.get("UOM", "")),
                division=_str(row.get("Division", "")),
                taxable=taxable,
            ))
        except Exception as e:
            errors.append(f"Row {i+2}: {e}")

    db.query(ProductMapping).delete()
    db.bulk_save_objects(records)
    db.commit()
    return ImportResponse(
        imported=len(records), skipped=len(errors), errors=errors,
        message=f"Product mapping refreshed: {len(records)} records loaded."
    )


# ══════════════════════════════════════════════════════════════════════════════
# PRICE MASTER
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/prices", response_model=List[PriceMasterResponse])
def list_prices(db: Session = Depends(get_db)):
    return db.query(PriceMaster).all()


@router.post("/prices", response_model=PriceMasterResponse)
def create_price(data: PriceMasterBase, db: Session = Depends(get_db)):
    rec = PriceMaster(**data.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.put("/prices/{id}", response_model=PriceMasterResponse)
def update_price(id: int, data: PriceMasterBase, db: Session = Depends(get_db)):
    rec = db.query(PriceMaster).filter(PriceMaster.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in data.model_dump().items():
        setattr(rec, k, v)
    db.commit()
    db.refresh(rec)
    return rec


@router.delete("/prices/{id}")
def delete_price(id: int, db: Session = Depends(get_db)):
    rec = db.query(PriceMaster).filter(PriceMaster.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(rec)
    db.commit()
    return {"deleted": id}


@router.post("/prices/import", response_model=ImportResponse)
async def import_prices(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Bulk import from the 'Pricing Mapping' sheet.
    Expected columns:
      Region, Sales District, Sold to party, SKU,
      MRP, MARGIN, OFFER, NLC, Validity from, Validy To
    """
    content = await file.read()
    try:
        df = _read_upload(file, content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot parse file: {e}")

    df.columns = [c.strip() for c in df.columns]

    records = []
    errors = []
    for i, row in df.iterrows():
        try:
            district = _str(row.get("Sales District", ""))
            sold_to = _str(row.get("Sold to party", ""))
            sku = _str(row.get("SKU", ""))
            nlc = _float(row.get("NLC"))
            if not district or not sold_to or not sku or nlc is None:
                errors.append(f"Row {i+2}: missing required field(s) — skipped")
                continue
            # Parse date strings like "01.05.2026"
            eff_from = _str(row.get("Validity from", ""))
            eff_to = _str(row.get("Validy To", ""))
            records.append(PriceMaster(
                region=_str(row.get("Region", "")),
                sales_district=district,
                sold_to_party=sold_to,
                sku_code=sku,
                mrp=_float(row.get("MRP")),
                margin=_float(row.get("MARGIN")),
                offer=_float(row.get("OFFER")),
                nlc=nlc,
                effective_from=eff_from,
                effective_to=eff_to,
            ))
        except Exception as e:
            errors.append(f"Row {i+2}: {e}")

    db.query(PriceMaster).delete()
    db.bulk_save_objects(records)
    db.commit()
    return ImportResponse(
        imported=len(records), skipped=len(errors), errors=errors,
        message=f"Price master refreshed: {len(records)} records loaded."
    )


# ══════════════════════════════════════════════════════════════════════════════
# LOCATION MAPPING (fallback / manual)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/locations", response_model=List[LocationMappingResponse])
def list_locations(db: Session = Depends(get_db)):
    return db.query(LocationMapping).all()


@router.post("/locations", response_model=LocationMappingResponse)
def create_location(data: LocationMappingBase, db: Session = Depends(get_db)):
    rec = LocationMapping(**data.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.put("/locations/{id}", response_model=LocationMappingResponse)
def update_location(id: int, data: LocationMappingBase, db: Session = Depends(get_db)):
    rec = db.query(LocationMapping).filter(LocationMapping.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in data.model_dump().items():
        setattr(rec, k, v)
    db.commit()
    db.refresh(rec)
    return rec


@router.delete("/locations/{id}")
def delete_location(id: int, db: Session = Depends(get_db)):
    rec = db.query(LocationMapping).filter(LocationMapping.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(rec)
    db.commit()
    return {"deleted": id}


# ══════════════════════════════════════════════════════════════════════════════
# INVENTORY
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/inventory", response_model=List[InventoryMasterResponse])
def list_inventory(db: Session = Depends(get_db)):
    return db.query(InventoryMaster).all()


@router.post("/inventory/import", response_model=ImportResponse)
async def import_inventory(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Bulk import inventory snapshot.
    Required columns: hfl_sku_code, plant_code, unrestricted_stock
    """
    content = await file.read()
    try:
        df = _read_upload(file, content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot parse file: {e}")

    df.columns = [c.strip() for c in df.columns]
    required = {"hfl_sku_code", "plant_code", "unrestricted_stock"}
    if not required.issubset(set(df.columns)):
        raise HTTPException(
            status_code=400,
            detail=f"Missing columns. Required: {required}. Got: {set(df.columns)}"
        )

    db.query(InventoryMaster).delete()
    records = []
    for _, row in df.iterrows():
        records.append(InventoryMaster(
            hfl_sku_code=str(row["hfl_sku_code"]),
            plant_code=str(row["plant_code"]),
            unrestricted_stock=float(row["unrestricted_stock"])
        ))
    db.bulk_save_objects(records)
    db.commit()
    return ImportResponse(
        imported=len(records), message=f"Inventory refreshed: {len(records)} records."
    )


# ══════════════════════════════════════════════════════════════════════════════
# CASE LOTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/case-lots", response_model=List[CaseLotMasterResponse])
def list_case_lots(db: Session = Depends(get_db)):
    return db.query(CaseLotMaster).all()


@router.post("/case-lots", response_model=CaseLotMasterResponse)
def create_case_lot(data: CaseLotMasterBase, db: Session = Depends(get_db)):
    rec = CaseLotMaster(**data.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.delete("/case-lots/{id}")
def delete_case_lot(id: int, db: Session = Depends(get_db)):
    rec = db.query(CaseLotMaster).filter(CaseLotMaster.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(rec)
    db.commit()
    return {"deleted": id}


@router.post("/case-lots/import", response_model=ImportResponse)
async def import_case_lots(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Bulk import from the 'CaseLot' sheet.
    Expected columns: Cluster, Sales District, Case Lot, SKU Code
    """
    content = await file.read()
    try:
        df = _read_upload(file, content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot parse file: {e}")

    df.columns = [c.strip() for c in df.columns]

    records = []
    errors = []
    for i, row in df.iterrows():
        try:
            cluster = _str(row.get("Cluster", ""))
            district = _str(row.get("Sales District", ""))
            sku = _str(row.get("SKU Code", ""))
            case_qty = _float(row.get("Case Lot"))
            if not cluster or not district or not sku or case_qty is None:
                errors.append(f"Row {i+2}: missing required field — skipped")
                continue
            records.append(CaseLotMaster(
                cluster=cluster,
                sales_district=district,
                case_qty=case_qty,
                sku_code=sku,
            ))
        except Exception as e:
            errors.append(f"Row {i+2}: {e}")

    db.query(CaseLotMaster).delete()
    db.bulk_save_objects(records)
    db.commit()
    return ImportResponse(
        imported=len(records), skipped=len(errors), errors=errors,
        message=f"Case lots refreshed: {len(records)} records loaded."
    )


# ══════════════════════════════════════════════════════════════════════════════
# SH-SKU-SO (Ship-to + SKU + Sales Office combinations)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/sh-sku-so", response_model=List[SHSKUSalesOfficeResponse])
def list_sh_sku_so(db: Session = Depends(get_db)):
    return db.query(SHSKUSalesOffice).all()


@router.post("/sh-sku-so/import", response_model=ImportResponse)
async def import_sh_sku_so(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Bulk import from the 'SH-SKU-SO' sheet.
    Expected columns: Sales Office, HFL Ship to code, HFL SKU Code, Material Description
    """
    content = await file.read()
    try:
        df = _read_upload(file, content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot parse file: {e}")

    df.columns = [c.strip() for c in df.columns]

    records = []
    errors = []
    for i, row in df.iterrows():
        try:
            so = _str(row.get("Sales Office", ""))
            ship_to = _str(row.get("HFL Ship to code", ""))
            sku = _str(row.get("HFL SKU Code", ""))
            if not so or not ship_to or not sku:
                errors.append(f"Row {i+2}: missing required field — skipped")
                continue
            records.append(SHSKUSalesOffice(
                sales_office=so,
                ship_to_code=ship_to,
                hfl_sku_code=sku,
                material_description=_str(row.get("Material Description", "")),
            ))
        except Exception as e:
            errors.append(f"Row {i+2}: {e}")

    db.query(SHSKUSalesOffice).delete()
    db.bulk_save_objects(records)
    db.commit()
    return ImportResponse(
        imported=len(records), skipped=len(errors), errors=errors,
        message=f"SH-SKU-SO mapping refreshed: {len(records)} records loaded."
    )


# ══════════════════════════════════════════════════════════════════════════════
# BULK IMPORT — single Excel with multiple sheets
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/import-all", response_model=dict)
async def import_all_sheets(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Import the complete mapping Excel file (all sheets at once).
    Detects sheets by name:
      'Customer Mapping', 'SKU Mapping', 'SH-SKU-SO', 'Pricing Mapping', 'CaseLot'
    """
    content = await file.read()
    try:
        xl = pd.ExcelFile(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot parse Excel: {e}")

    results = {}

    # ── Customer Mapping ──
    if "Customer Mapping" in xl.sheet_names:
        df = xl.parse("Customer Mapping")
        df.columns = [c.strip() for c in df.columns]
        records, errors = [], []
        for i, row in df.iterrows():
            cluster = _str(row.get("Cluster", ""))
            if not cluster:
                errors.append(f"Row {i+2}: missing Cluster")
                continue
            records.append(CustomerMapping(
                cluster=cluster,
                state=_str(row.get("State", "")),
                gst_number=_str(row.get("GST Number", "")),
                full_address=_str(row.get("Full Address as per PO", "")),
                site_code=_str(row.get("Site code/Vendor loc unique code(As mentioned in PO)", "")),
                sales_district=_str(row.get("Sales District", "")),
                sold_to_party=_str(row.get("Sold to party code", "")),
                ship_to_party_code=_str(row.get("Ship to Party Code", "")),
                sales_office=_str(row.get("Sales office", "")),
                person_responsible=_str(row.get("Person Responsible", "")),
                email_id=_str(row.get("Email Id", "")),
                contact_number=_str(row.get("Contact Number", "")),
            ))
        db.query(CustomerMapping).delete()
        db.bulk_save_objects(records)
        results["customer_mapping"] = {"imported": len(records), "errors": errors}

    # ── SKU Mapping ──
    if "SKU Mapping" in xl.sheet_names:
        df = xl.parse("SKU Mapping")
        df.columns = [c.strip() for c in df.columns]
        records, errors = [], []
        for i, row in df.iterrows():
            sold_to = _str(row.get("Sold to Party", ""))
            hfl_code = _str(row.get("HFL SKU CODE", ""))
            if not sold_to or not hfl_code:
                errors.append(f"Row {i+2}: missing Sold to Party or HFL SKU CODE")
                continue
            taxable_val = _str(row.get("Taxable or Non Taxable", "Taxable"))
            records.append(ProductMapping(
                sold_to_party=sold_to,
                customer_sku=_str(row.get("Customer SKU", "")),
                customer_product_text=_str(row.get("Customer SKU Description", "")),
                hfl_sku_code=hfl_code,
                description=_str(row.get("Description", "")),
                uom=_str(row.get("UOM", "")),
                division=_str(row.get("Division", "")),
                taxable="non" not in taxable_val.lower(),
            ))
        db.query(ProductMapping).delete()
        db.bulk_save_objects(records)
        results["sku_mapping"] = {"imported": len(records), "errors": errors}

    # ── Pricing Mapping ──
    if "Pricing Mapping" in xl.sheet_names:
        df = xl.parse("Pricing Mapping")
        df.columns = [c.strip() for c in df.columns]
        records, errors = [], []
        for i, row in df.iterrows():
            district = _str(row.get("Sales District", ""))
            sold_to = _str(row.get("Sold to party", ""))
            sku = _str(row.get("SKU", ""))
            nlc = _float(row.get("NLC"))
            if not district or not sold_to or not sku or nlc is None:
                errors.append(f"Row {i+2}: missing required field")
                continue
            records.append(PriceMaster(
                region=_str(row.get("Region", "")),
                sales_district=district,
                sold_to_party=sold_to,
                sku_code=sku,
                mrp=_float(row.get("MRP")),
                margin=_float(row.get("MARGIN")),
                offer=_float(row.get("OFFER")),
                nlc=nlc,
                effective_from=_str(row.get("Validity from", "")),
                effective_to=_str(row.get("Validy To", "")),
            ))
        db.query(PriceMaster).delete()
        db.bulk_save_objects(records)
        results["pricing_mapping"] = {"imported": len(records), "errors": errors}

    # ── SH-SKU-SO ──
    if "SH-SKU-SO" in xl.sheet_names:
        df = xl.parse("SH-SKU-SO")
        df.columns = [c.strip() for c in df.columns]
        records, errors = [], []
        for i, row in df.iterrows():
            so = _str(row.get("Sales Office", ""))
            ship_to = _str(row.get("HFL Ship to code", ""))
            sku = _str(row.get("HFL SKU Code", ""))
            if not so or not ship_to or not sku:
                errors.append(f"Row {i+2}: missing required field")
                continue
            records.append(SHSKUSalesOffice(
                sales_office=so,
                ship_to_code=ship_to,
                hfl_sku_code=sku,
                material_description=_str(row.get("Material Description", "")),
            ))
        db.query(SHSKUSalesOffice).delete()
        db.bulk_save_objects(records)
        results["sh_sku_so"] = {"imported": len(records), "errors": errors}

    # ── CaseLot ──
    if "CaseLot" in xl.sheet_names:
        df = xl.parse("CaseLot")
        df.columns = [c.strip() for c in df.columns]
        records, errors = [], []
        for i, row in df.iterrows():
            cluster = _str(row.get("Cluster", ""))
            district = _str(row.get("Sales District", ""))
            sku = _str(row.get("SKU Code", ""))
            case_qty = _float(row.get("Case Lot"))
            if not cluster or not district or not sku or case_qty is None:
                errors.append(f"Row {i+2}: missing required field")
                continue
            records.append(CaseLotMaster(
                cluster=cluster,
                sales_district=district,
                case_qty=case_qty,
                sku_code=sku,
            ))
        db.query(CaseLotMaster).delete()
        db.bulk_save_objects(records)
        results["case_lots"] = {"imported": len(records), "errors": errors}

    db.commit()
    total = sum(r.get("imported", 0) for r in results.values())
    return {"total_imported": total, "sheets": results, "message": "All sheets imported successfully"}