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

// ── Master Data ────────────────────────────────────────────────────────────
export const getProducts     = () => request<ProductMapping[]>('/master-data/products')
export const createProduct   = (d: Omit<ProductMapping,'id'|'updated_at'>) => request<ProductMapping>('/master-data/products', { method: 'POST', body: JSON.stringify(d) })
export const updateProduct   = (id: number, d: Omit<ProductMapping,'id'|'updated_at'>) => request<ProductMapping>(`/master-data/products/${id}`, { method: 'PUT', body: JSON.stringify(d) })
export const deleteProduct   = (id: number) => request(`/master-data/products/${id}`, { method: 'DELETE' })

export const getPrices       = () => request<PriceMaster[]>('/master-data/prices')
export const createPrice     = (d: Omit<PriceMaster,'id'|'updated_at'>) => request<PriceMaster>('/master-data/prices', { method: 'POST', body: JSON.stringify(d) })
export const updatePrice     = (id: number, d: Omit<PriceMaster,'id'|'updated_at'>) => request<PriceMaster>(`/master-data/prices/${id}`, { method: 'PUT', body: JSON.stringify(d) })
export const deletePrice     = (id: number) => request(`/master-data/prices/${id}`, { method: 'DELETE' })

export const getLocations    = () => request<LocationMapping[]>('/master-data/locations')
export const createLocation  = (d: Omit<LocationMapping,'id'|'updated_at'>) => request<LocationMapping>('/master-data/locations', { method: 'POST', body: JSON.stringify(d) })
export const deleteLocation  = (id: number) => request(`/master-data/locations/${id}`, { method: 'DELETE' })

export const getInventory    = () => request<InventoryItem[]>('/master-data/inventory')

export const getCaseLots     = () => request<CaseLot[]>('/master-data/case-lots')
export const createCaseLot   = (d: Omit<CaseLot,'id'|'updated_at'>) => request<CaseLot>('/master-data/case-lots', { method: 'POST', body: JSON.stringify(d) })
export const deleteCaseLot   = (id: number) => request(`/master-data/case-lots/${id}`, { method: 'DELETE' })

// ── Types ──────────────────────────────────────────────────────────────────

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
  description: string | null
  uom: string | null
  hsn_code: string | null
  qty: number | null
  unit_price: number | null
  mrp: number | null
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

export interface ProductMapping {
  id: number
  customer_product_text: string
  sap_material_code: string
  sap_product_description: string | null
  customer_code: string | null
  updated_at: string | null
}

export interface PriceMaster {
  id: number
  customer_code: string
  sap_material_code: string
  approved_price: number
  effective_from: string | null
  effective_to: string | null
  updated_at: string | null
}

export interface LocationMapping {
  id: number
  customer_code: string
  address_pattern: string
  sap_ship_to_code: string
  city: string | null
  state: string | null
  updated_at: string | null
}

export interface InventoryItem {
  id: number
  sap_material_code: string
  plant_code: string
  unrestricted_stock: number
  last_refreshed: string | null
}

export interface CaseLot {
  id: number
  sap_material_code: string
  sales_district: string
  case_qty: number
  updated_at: string | null
}