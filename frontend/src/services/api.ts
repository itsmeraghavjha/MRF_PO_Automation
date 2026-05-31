const BASE = '/api/v1'

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
    ...opts,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

// ── Dashboard ──────────────────────────────────────────────────────────────
export const getDashboard = () => request<DashboardResponse>('/dashboard')

// ── Orders ─────────────────────────────────────────────────────────────────
export const getOrders = (params?: OrderParams) => {
  const q = new URLSearchParams()
  if (params?.page) q.set('page', String(params.page))
  if (params?.page_size) q.set('page_size', String(params.page_size))
  if (params?.status) q.set('status', params.status)
  if (params?.search) q.set('search', params.search)
  return request<OrderListResponse>(`/orders?${q}`)
}

export const getOrder = (id: number) => request<OrderDetail>(`/orders/${id}`)

export const updateLineItem = (orderId: number, itemId: number, data: LineItemUpdate) =>
  request(`/orders/${orderId}/line-items/${itemId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })

export const revalidateOrder = (orderId: number) =>
  request<RevalidateResponse>(`/orders/${orderId}/revalidate`, { method: 'POST' })

export const pushToSAP = (orderId: number) =>
  request<SAPPushResponse>(`/orders/${orderId}/push-sap`, { method: 'POST' })

// ── Master Data — Customers ────────────────────────────────────────────────
export const getCustomers    = () => request<CustomerMapping[]>('/master-data/customers')
export const createCustomer  = (d: Omit<CustomerMapping, 'id' | 'updated_at'>) => request<CustomerMapping>('/master-data/customers', { method: 'POST', body: JSON.stringify(d) })
export const updateCustomer  = (id: number, d: Omit<CustomerMapping, 'id' | 'updated_at'>) => request<CustomerMapping>(`/master-data/customers/${id}`, { method: 'PUT', body: JSON.stringify(d) })
export const deleteCustomer  = (id: number) => request(`/master-data/customers/${id}`, { method: 'DELETE' })

// ── Master Data — Products (SKU Mapping) ──────────────────────────────────
export const getProducts     = () => request<ProductMapping[]>('/master-data/products')
export const createProduct   = (d: Omit<ProductMapping, 'id' | 'updated_at'>) => request<ProductMapping>('/master-data/products', { method: 'POST', body: JSON.stringify(d) })
export const updateProduct   = (id: number, d: Omit<ProductMapping, 'id' | 'updated_at'>) => request<ProductMapping>(`/master-data/products/${id}`, { method: 'PUT', body: JSON.stringify(d) })
export const deleteProduct   = (id: number) => request(`/master-data/products/${id}`, { method: 'DELETE' })

// ── Master Data — Prices ───────────────────────────────────────────────────
export const getPrices       = () => request<PriceMaster[]>('/master-data/prices')
export const createPrice     = (d: Omit<PriceMaster, 'id' | 'updated_at'>) => request<PriceMaster>('/master-data/prices', { method: 'POST', body: JSON.stringify(d) })
export const updatePrice     = (id: number, d: Omit<PriceMaster, 'id' | 'updated_at'>) => request<PriceMaster>(`/master-data/prices/${id}`, { method: 'PUT', body: JSON.stringify(d) })
export const deletePrice     = (id: number) => request(`/master-data/prices/${id}`, { method: 'DELETE' })

// ── Master Data — Locations ────────────────────────────────────────────────
export const getLocations    = () => request<LocationMapping[]>('/master-data/locations')
export const createLocation  = (d: Omit<LocationMapping, 'id' | 'updated_at'>) => request<LocationMapping>('/master-data/locations', { method: 'POST', body: JSON.stringify(d) })
export const updateLocation  = (id: number, d: Omit<LocationMapping, 'id' | 'updated_at'>) => request<LocationMapping>(`/master-data/locations/${id}`, { method: 'PUT', body: JSON.stringify(d) })
export const deleteLocation  = (id: number) => request(`/master-data/locations/${id}`, { method: 'DELETE' })

// ── Master Data — Districts ────────────────────────────────────────────────
export const getDistricts    = () => request<DistrictMapping[]>('/master-data/districts')
export const createDistrict  = (d: Omit<DistrictMapping, 'id' | 'updated_at'>) => request<DistrictMapping>('/master-data/districts', { method: 'POST', body: JSON.stringify(d) })
export const updateDistrict  = (id: number, d: Omit<DistrictMapping, 'id' | 'updated_at'>) => request<DistrictMapping>(`/master-data/districts/${id}`, { method: 'PUT', body: JSON.stringify(d) })
export const deleteDistrict  = (id: number) => request(`/master-data/districts/${id}`, { method: 'DELETE' })

// ── Master Data — Inventory ────────────────────────────────────────────────
export const getInventory    = () => request<InventoryItem[]>('/master-data/inventory')

// ── Master Data — Case Lots ────────────────────────────────────────────────
export const getCaseLots     = () => request<CaseLot[]>('/master-data/case-lots')
export const createCaseLot   = (d: Omit<CaseLot, 'id' | 'updated_at'>) => request<CaseLot>('/master-data/case-lots', { method: 'POST', body: JSON.stringify(d) })
export const deleteCaseLot   = (id: number) => request(`/master-data/case-lots/${id}`, { method: 'DELETE' })

// ── Master Data — SH-SKU-SO ────────────────────────────────────────────────
export const getShSkuSo      = () => request<ShSkuSo[]>('/master-data/sh-sku-so')

// ── Bulk Import ────────────────────────────────────────────────────────────
export const importAllSheets = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return fetch(`${BASE}/master-data/import-all`, { method: 'POST', body: form }).then(r => r.json())
}

// ═══════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════

export interface DashboardKPIs {
  total_pos_today: number
  total_pos_all_time: number
  total_value_today: number
  total_value_all_time: number
  auto_processed: number
  exceptions_pending: number
  sap_pushed: number
  success_rate: number
}

export interface StatusBreakdown {
  status: string
  count: number
  label: string
  color: string
}

export interface DashboardResponse {
  kpis: DashboardKPIs
  status_breakdown: StatusBreakdown[]
  recent_orders: OrderSummary[]
}

export interface OrderSummary {
  id: number
  po_number: string
  po_date: string | null
  customer_code: string | null
  customer_name: string | null
  sold_to_party: string | null
  status: string
  total_value: number | null
  email_sender: string | null
  rejection_summary: string | null
  created_at: string
  updated_at: string | null
  line_item_count: number
  failed_line_count: number
}

export interface LineItem {
  id: number
  order_id: number
  material_code: string | null
  customer_sku: string | null
  description: string | null
  uom: string | null
  hsn_code: string | null
  qty: number | null
  unit_price: number | null
  mrp: number | null
  nlc: number | null
  tax_rate: number | null
  tax_amount: number | null
  line_total: number | null
  is_valid: boolean
  rejection_reason: string | null
}

export interface AuditLog {
  id: number
  event_type: string
  description: string | null
  performed_by: string
  created_at: string
}

export interface OrderDetail extends OrderSummary {
  vendor_gstin: string | null
  ship_to_code: string | null
  ship_to_address: string | null
  site_code: string | null
  sales_district: string | null
  sales_office: string | null
  delivery_date: string | null
  expiry_date: string | null
  email_uid: string | null
  email_subject: string | null
  drive_link: string | null
  is_update: boolean
  line_items: LineItem[]
  audit_logs: AuditLog[]
}

export interface OrderListResponse {
  orders: OrderSummary[]
  total: number
  page: number
  page_size: number
}

export interface OrderParams {
  page?: number
  page_size?: number
  status?: string
  search?: string
}

export interface LineItemUpdate {
  material_code?: string
  qty?: number
  unit_price?: number
}

export interface RevalidateResponse {
  order_id: number
  all_passed: boolean
  new_status: string
  validation_results: ValidationResult[]
}

export interface ValidationResult {
  rule_id: string
  rule_name: string
  passed: boolean
  failure_reason: string | null
}

export interface SAPPushResponse {
  order_id: number
  po_number: string
  csv_filename: string
  pushed_at: string
}

// ── Master Data Types ──────────────────────────────────────────────────────

/** CustomerMapping — one row per physical ship-to location per cluster */
export interface CustomerMapping {
  id: number
  cluster: string                    // e.g. RRL, DMT
  state: string | null
  gst_number: string | null          // customer GST on PO
  full_address: string | null        // full address as printed on PO
  site_code: string | null           // vendor loc / site code on PO (e.g. 2999)
  sold_to_party: string | null       // SAP sold-to (e.g. 250029)
  ship_to_party_code: string | null  // SAP ship-to (e.g. 273774)
  sales_district: string | null      // e.g. APBB01-Bobbili
  sales_office: string | null        // e.g. 1961-Bobbili Sales Office
  person_responsible: string | null
  email_id: string | null
  contact_number: string | null
  updated_at: string | null
}

/** ProductMapping — customer SKU → HFL SAP material code */
export interface ProductMapping {
  id: number
  sold_to_party: string              // SAP sold-to (e.g. 250001)
  customer_sku: string | null        // customer's article code on PO
  customer_product_text: string | null
  hfl_sku_code: string               // HFL SAP material code (e.g. 10017)
  description: string | null
  uom: string | null
  division: string | null
  taxable: boolean
  updated_at: string | null
}

/** PriceMaster — NLC per sold-to + sales district + SKU */
export interface PriceMaster {
  id: number
  region: string | null
  sales_district: string             // e.g. APBB01-Bobbili
  sold_to_party: string              // e.g. 250029
  sku_code: string                   // HFL SKU code (e.g. 70004)
  mrp: number | null
  margin: number | null
  offer: number | null
  nlc: number                        // Net Landing Cost — approved price
  effective_from: string | null
  effective_to: string | null
  updated_at: string | null
}

/** LocationMapping — fallback address-pattern → SAP ship-to */
export interface LocationMapping {
  id: number
  cluster: string
  address_pattern: string
  sap_ship_to_code: string
  sales_district: string | null
  city: string | null
  state: string | null
  updated_at: string | null
}

/** DistrictMapping — SAP ship-to code → sales district */
export interface DistrictMapping {
  id: number
  ship_to_code: string
  sales_district: string
  cluster: string | null
  updated_at: string | null
}

/** InventoryMaster — unrestricted stock per HFL SKU + plant */
export interface InventoryItem {
  id: number
  hfl_sku_code: string
  plant_code: string
  unrestricted_stock: number
  last_refreshed: string | null
}

/** CaseLotMaster — min order multiples per cluster + district + SKU */
export interface CaseLot {
  id: number
  cluster: string
  sales_district: string
  case_qty: number
  sku_code: string                   // HFL SKU code
  updated_at: string | null
}

/** SHSKUSalesOffice — valid Sales Office + Ship-to + SKU combos */
export interface ShSkuSo {
  id: number
  sales_office: string
  ship_to_code: string
  hfl_sku_code: string
  material_description: string | null
  updated_at: string | null
}


 
// ── Vendor / Delivery Confirmation (Phase 3) ──────────────────────────────
 
export const sendDeliveryRequest = (orderId: number) =>
  request<DeliveryRequestResponse>(`/orders/${orderId}/send-delivery-request`, { method: 'POST' })
 
export const getTokenStatus = (token: string) =>
  request<DeliveryTokenStatus>(`/vendor/token-status/${token}`)
 
// ── Types ──────────────────────────────────────────────────────────────────
 
export interface DeliveryRequestResponse {
  success: boolean
  token: string
  recipient: string
  email_sent: boolean
  expires_at: string
  portal_url: string
}
 
export interface DeliveryTokenStatus {
  token: string
  order_id: number
  po_number: string | null
  recipient_email: string
  status: 'PENDING' | 'VISITED' | 'UPDATED' | 'EXPIRED'
  expires_at: string | null
  created_at: string | null
  current_delivery_date: string | null
}