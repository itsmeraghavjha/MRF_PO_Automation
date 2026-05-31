from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
import io

from app.db.base import get_db
from app.models.models import (
    ProductMapping, PriceMaster, LocationMapping,
    InventoryMaster, CaseLotMaster, DistrictMapping, CustomerMapping
)
from app.schemas.schemas import (
    ProductMappingBase, ProductMappingResponse,
    PriceMasterBase, PriceMasterResponse,
    LocationMappingBase, LocationMappingResponse,
    InventoryMasterBase, InventoryMasterResponse,
    CaseLotMasterBase, CaseLotMasterResponse,
)

router = APIRouter(prefix="/master-data", tags=["master-data"])


# ── Product Mapping ──────────────────────────────────────────────────────────

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


# ── Price Master ──────────────────────────────────────────────────────────────

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


# ── Location Mapping ──────────────────────────────────────────────────────────

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


# ── Inventory ──────────────────────────────────────────────────────────────────

@router.get("/inventory", response_model=List[InventoryMasterResponse])
def list_inventory(db: Session = Depends(get_db)):
    return db.query(InventoryMaster).all()


@router.post("/inventory/import")
async def import_inventory(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Bulk import inventory from Excel/CSV. Performs full refresh (delete + re-import)."""
    content = await file.read()

    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {e}")

    required_cols = {"sap_material_code", "plant_code", "unrestricted_stock"}
    if not required_cols.issubset(set(df.columns)):
        raise HTTPException(
            status_code=400,
            detail=f"Missing columns. Required: {required_cols}. Got: {set(df.columns)}"
        )

    # Full refresh
    db.query(InventoryMaster).delete()

    records = []
    for _, row in df.iterrows():
        records.append(InventoryMaster(
            sap_material_code=str(row["sap_material_code"]),
            plant_code=str(row["plant_code"]),
            unrestricted_stock=float(row["unrestricted_stock"])
        ))

    db.bulk_save_objects(records)
    db.commit()

    return {"imported": len(records), "message": "Inventory refreshed successfully"}


# ── Case Lot ──────────────────────────────────────────────────────────────────

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