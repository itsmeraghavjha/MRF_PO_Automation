"""
SAP CSV Generation Service — generates standardised SAP upload CSV files.
Segments line items into taxable (Sno=2) and non-taxable (Sno=1) rows.
"""
import csv
import os
import logging
from datetime import datetime
from pathlib import Path
from app.core.config import settings
from app.models.models import OrderLedger

logger = logging.getLogger(__name__)


def generate_sap_csv(order: OrderLedger) -> tuple[str, str]:
    """
    Generate SAP CSV for a validated order.
    Returns (filename, full_path)
    """
    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"SAP_{order.po_number}_{timestamp}.csv"

    output_dir = Path(settings.SAP_OUTPUT_FOLDER)
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename

    rows = []

    for item in order.line_items:
        tax_rate = item.tax_rate or 0

        if tax_rate > 0:
            # Taxable item — two rows: Sno=1 (base) and Sno=2 (tax)
            base_amount = (item.qty or 0) * (item.unit_price or 0)
            tax_amount = item.tax_amount or (base_amount * tax_rate / 100)

            rows.append({
                "Sno": 1,
                "Order_No": order.po_number,
                "Order_Date": order.po_date or "",
                "Ship_To": order.ship_to_code or "",
                "Material_Code": item.material_code or "",
                "Description": item.description or "",
                "UOM": item.uom or "",
                "HSN_Code": item.hsn_code or "",
                "Quantity": item.qty or 0,
                "Unit_Price": item.unit_price or 0,
                "Tax_Rate": 0,
                "Tax_Amount": 0,
                "Line_Total": base_amount,
                "Taxable": "",
                "Customer_Code": order.customer_code or "",
                "GSTIN": order.vendor_gstin or "",
                "Delivery_Date": order.delivery_date or "",
            })

            rows.append({
                "Sno": 2,
                "Order_No": order.po_number,
                "Order_Date": order.po_date or "",
                "Ship_To": order.ship_to_code or "",
                "Material_Code": item.material_code or "",
                "Description": f"{item.description or ''} - GST {tax_rate}%",
                "UOM": item.uom or "",
                "HSN_Code": item.hsn_code or "",
                "Quantity": item.qty or 0,
                "Unit_Price": item.unit_price or 0,
                "Tax_Rate": tax_rate,
                "Tax_Amount": tax_amount,
                "Line_Total": base_amount + tax_amount,
                "Taxable": "X",
                "Customer_Code": order.customer_code or "",
                "GSTIN": order.vendor_gstin or "",
                "Delivery_Date": order.delivery_date or "",
            })
        else:
            # Non-taxable item — single row Sno=1
            rows.append({
                "Sno": 1,
                "Order_No": order.po_number,
                "Order_Date": order.po_date or "",
                "Ship_To": order.ship_to_code or "",
                "Material_Code": item.material_code or "",
                "Description": item.description or "",
                "UOM": item.uom or "",
                "HSN_Code": item.hsn_code or "",
                "Quantity": item.qty or 0,
                "Unit_Price": item.unit_price or 0,
                "Tax_Rate": 0,
                "Tax_Amount": 0,
                "Line_Total": (item.qty or 0) * (item.unit_price or 0),
                "Taxable": "",
                "Customer_Code": order.customer_code or "",
                "GSTIN": order.vendor_gstin or "",
                "Delivery_Date": order.delivery_date or "",
            })

    fieldnames = [
        "Sno", "Order_No", "Order_Date", "Ship_To", "Material_Code",
        "Description", "UOM", "HSN_Code", "Quantity", "Unit_Price",
        "Tax_Rate", "Tax_Amount", "Line_Total", "Taxable",
        "Customer_Code", "GSTIN", "Delivery_Date"
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"SAP CSV generated: {filepath} ({len(rows)} rows)")
    return filename, str(filepath)