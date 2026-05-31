import { useEffect, useState } from 'react'
import { Plus, Trash2, RefreshCw, Upload } from 'lucide-react'
import {
  getProducts, createProduct, deleteProduct,
  getPrices, createPrice, deletePrice,
  getLocations, createLocation, deleteLocation,
  getInventory, getCaseLots, createCaseLot, deleteCaseLot,
  type ProductMapping, type PriceMaster, type LocationMapping,
  type InventoryItem, type CaseLot
} from '../services/api'

type Tab = 'products' | 'prices' | 'locations' | 'inventory' | 'caselots'

export default function MasterDataPage() {
  const [activeTab, setActiveTab] = useState<Tab>('products')

  const tabs: { key: Tab; label: string; desc: string }[] = [
    { key: 'products', label: 'Product Mapping', desc: 'Customer SKU → SAP material code' },
    { key: 'prices', label: 'Price Master', desc: 'Approved prices per customer' },
    { key: 'locations', label: 'Location Mapping', desc: 'Ship-to address → SAP code' },
    { key: 'inventory', label: 'Inventory', desc: 'Live stock levels' },
    { key: 'caselots', label: 'Case Lots', desc: 'Min order quantities by district' },
  ]

  return (
    <div style={{ padding: '28px' }} className="animate-fade">
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 24, fontWeight: 800, fontFamily: 'var(--font-display)', marginBottom: 4 }}>
          Master Data
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, margin: 0 }}>
          Manage reference data used during PO validation
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid var(--border)', paddingBottom: 0 }}>
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              padding: '10px 14px', fontSize: 13, fontWeight: 500,
              color: activeTab === tab.key ? 'var(--text-primary)' : 'var(--text-muted)',
              borderBottom: activeTab === tab.key ? '2px solid var(--accent-amber)' : '2px solid transparent',
              marginBottom: -1, transition: 'all 0.15s', whiteSpace: 'nowrap'
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'products' && <ProductsTab />}
      {activeTab === 'prices' && <PricesTab />}
      {activeTab === 'locations' && <LocationsTab />}
      {activeTab === 'inventory' && <InventoryTab />}
      {activeTab === 'caselots' && <CaseLotsTab />}
    </div>
  )
}

// ─── Products ────────────────────────────────────────────────────────────────

function ProductsTab() {
  const [items, setItems] = useState<ProductMapping[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ customer_product_text: '', sap_material_code: '', sap_product_description: '', customer_code: '' })

  const load = async () => { setLoading(true); setItems(await getProducts().catch(() => [])); setLoading(false) }
  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    await createProduct(form)
    setForm({ customer_product_text: '', sap_material_code: '', sap_product_description: '', customer_code: '' })
    setShowForm(false)
    load()
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{items.length} mappings</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm btn-icon" onClick={load}><RefreshCw size={13} /></button>
          <button className="btn btn-primary btn-sm" onClick={() => setShowForm(!showForm)}>
            <Plus size={13} /> Add Mapping
          </button>
        </div>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: 16, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <FormField label="Customer Product Text" value={form.customer_product_text} onChange={v => setForm(f => ({...f, customer_product_text: v}))} flex={2} />
          <FormField label="SAP Material Code" value={form.sap_material_code} onChange={v => setForm(f => ({...f, sap_material_code: v}))} />
          <FormField label="SAP Description" value={form.sap_product_description} onChange={v => setForm(f => ({...f, sap_product_description: v}))} />
          <FormField label="Customer Code" value={form.customer_code} onChange={v => setForm(f => ({...f, customer_code: v}))} />
          <button className="btn btn-primary btn-sm" onClick={handleCreate}>Save</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>Cancel</button>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <LoadingRow /> : (
          <table className="data-table">
            <thead><tr><th>Customer Text</th><th>SAP Code</th><th>SAP Description</th><th>Customer</th><th></th></tr></thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id}>
                  <td style={{ fontSize: 12 }}>{item.customer_product_text}</td>
                  <td className="mono-data">{item.sap_material_code}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{item.sap_product_description || '—'}</td>
                  <td><CustomerTag code={item.customer_code} /></td>
                  <td>
                    <button className="btn btn-danger btn-sm btn-icon" onClick={async () => { await deleteProduct(item.id); load() }}>
                      <Trash2 size={11} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && items.length === 0 && <EmptyRow message="No product mappings. Add one above." />}
      </div>
    </div>
  )
}

// ─── Prices ──────────────────────────────────────────────────────────────────

function PricesTab() {
  const [items, setItems] = useState<PriceMaster[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ customer_code: '', sap_material_code: '', approved_price: '' })

  const load = async () => { setLoading(true); setItems(await getPrices().catch(() => [])); setLoading(false) }
  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    await createPrice({ ...form, approved_price: Number(form.approved_price), effective_from: null, effective_to: null })
    setForm({ customer_code: '', sap_material_code: '', approved_price: '' })
    setShowForm(false)
    load()
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{items.length} price records</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm btn-icon" onClick={load}><RefreshCw size={13} /></button>
          <button className="btn btn-primary btn-sm" onClick={() => setShowForm(!showForm)}>
            <Plus size={13} /> Add Price
          </button>
        </div>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: 16, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <FormField label="Customer Code" value={form.customer_code} onChange={v => setForm(f => ({...f, customer_code: v}))} />
          <FormField label="SAP Material Code" value={form.sap_material_code} onChange={v => setForm(f => ({...f, sap_material_code: v}))} />
          <FormField label="Approved Price (₹)" value={form.approved_price} onChange={v => setForm(f => ({...f, approved_price: v}))} type="number" />
          <button className="btn btn-primary btn-sm" onClick={handleCreate}>Save</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>Cancel</button>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <LoadingRow /> : (
          <table className="data-table">
            <thead><tr><th>Customer</th><th>Material Code</th><th>Approved Price</th><th>Effective From</th><th>Effective To</th><th></th></tr></thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id}>
                  <td><CustomerTag code={item.customer_code} /></td>
                  <td className="mono-data">{item.sap_material_code}</td>
                  <td className="mono-data" style={{ color: '#10b981' }}>₹{item.approved_price.toLocaleString('en-IN')}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{item.effective_from || '—'}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{item.effective_to || '—'}</td>
                  <td>
                    <button className="btn btn-danger btn-sm btn-icon" onClick={async () => { await deletePrice(item.id); load() }}>
                      <Trash2 size={11} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && items.length === 0 && <EmptyRow message="No price records." />}
      </div>
    </div>
  )
}

// ─── Locations ───────────────────────────────────────────────────────────────

function LocationsTab() {
  const [items, setItems] = useState<LocationMapping[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ customer_code: '', address_pattern: '', sap_ship_to_code: '', city: '', state: '' })

  const load = async () => { setLoading(true); setItems(await getLocations().catch(() => [])); setLoading(false) }
  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    await createLocation(form)
    setForm({ customer_code: '', address_pattern: '', sap_ship_to_code: '', city: '', state: '' })
    setShowForm(false)
    load()
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{items.length} location mappings</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm btn-icon" onClick={load}><RefreshCw size={13} /></button>
          <button className="btn btn-primary btn-sm" onClick={() => setShowForm(!showForm)}>
            <Plus size={13} /> Add Location
          </button>
        </div>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: 16, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <FormField label="Customer Code" value={form.customer_code} onChange={v => setForm(f => ({...f, customer_code: v}))} />
          <FormField label="Address Pattern" value={form.address_pattern} onChange={v => setForm(f => ({...f, address_pattern: v}))} flex={2} />
          <FormField label="SAP Ship-to Code" value={form.sap_ship_to_code} onChange={v => setForm(f => ({...f, sap_ship_to_code: v}))} />
          <FormField label="City" value={form.city} onChange={v => setForm(f => ({...f, city: v}))} />
          <FormField label="State" value={form.state} onChange={v => setForm(f => ({...f, state: v}))} />
          <button className="btn btn-primary btn-sm" onClick={handleCreate}>Save</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>Cancel</button>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <LoadingRow /> : (
          <table className="data-table">
            <thead><tr><th>Customer</th><th>Address Pattern</th><th>SAP Ship-to Code</th><th>City</th><th>State</th><th></th></tr></thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id}>
                  <td><CustomerTag code={item.customer_code} /></td>
                  <td style={{ fontSize: 11, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.address_pattern}</td>
                  <td className="mono-data">{item.sap_ship_to_code}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{item.city || '—'}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{item.state || '—'}</td>
                  <td>
                    <button className="btn btn-danger btn-sm btn-icon" onClick={async () => { await deleteLocation(item.id); load() }}>
                      <Trash2 size={11} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && items.length === 0 && <EmptyRow message="No location mappings." />}
      </div>
    </div>
  )
}

// ─── Inventory ───────────────────────────────────────────────────────────────

function InventoryTab() {
  const [items, setItems] = useState<InventoryItem[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => { setLoading(true); setItems(await getInventory().catch(() => [])); setLoading(false) }
  useEffect(() => { load() }, [])

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{items.length} stock records</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm btn-icon" onClick={load}><RefreshCw size={13} /></button>
          <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
            <Upload size={13} /> Import CSV/Excel
            <input type="file" accept=".csv,.xlsx,.xls" style={{ display: 'none' }} onChange={async (e) => {
              const file = e.target.files?.[0]
              if (!file) return
              const form = new FormData()
              form.append('file', file)
              await fetch('/api/v1/master-data/inventory/import', { method: 'POST', body: form })
              load()
              e.target.value = ''
            }} />
          </label>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <LoadingRow /> : (
          <table className="data-table">
            <thead><tr><th>Material Code</th><th>Plant</th><th>Unrestricted Stock</th><th>Last Refreshed</th></tr></thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id}>
                  <td className="mono-data">{item.sap_material_code}</td>
                  <td className="mono-data">{item.plant_code}</td>
                  <td>
                    <span style={{
                      fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600,
                      color: item.unrestricted_stock > 100 ? '#10b981' : item.unrestricted_stock > 0 ? '#f59e0b' : '#ef4444'
                    }}>
                      {item.unrestricted_stock.toLocaleString('en-IN')}
                    </span>
                  </td>
                  <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.last_refreshed ? new Date(item.last_refreshed).toLocaleString('en-IN') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && items.length === 0 && <EmptyRow message="No inventory data. Import a CSV/Excel file." />}
      </div>
    </div>
  )
}

// ─── Case Lots ────────────────────────────────────────────────────────────────

function CaseLotsTab() {
  const [items, setItems] = useState<CaseLot[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ sap_material_code: '', sales_district: '', case_qty: '' })

  const load = async () => { setLoading(true); setItems(await getCaseLots().catch(() => [])); setLoading(false) }
  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    await createCaseLot({ ...form, case_qty: Number(form.case_qty) })
    setForm({ sap_material_code: '', sales_district: '', case_qty: '' })
    setShowForm(false)
    load()
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{items.length} case lot rules</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm btn-icon" onClick={load}><RefreshCw size={13} /></button>
          <button className="btn btn-primary btn-sm" onClick={() => setShowForm(!showForm)}>
            <Plus size={13} /> Add Rule
          </button>
        </div>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: 16, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <FormField label="SAP Material Code" value={form.sap_material_code} onChange={v => setForm(f => ({...f, sap_material_code: v}))} />
          <FormField label="Sales District" value={form.sales_district} onChange={v => setForm(f => ({...f, sales_district: v}))} />
          <FormField label="Case Qty" value={form.case_qty} onChange={v => setForm(f => ({...f, case_qty: v}))} type="number" />
          <button className="btn btn-primary btn-sm" onClick={handleCreate}>Save</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>Cancel</button>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <LoadingRow /> : (
          <table className="data-table">
            <thead><tr><th>Material Code</th><th>Sales District</th><th>Case Qty</th><th></th></tr></thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id}>
                  <td className="mono-data">{item.sap_material_code}</td>
                  <td style={{ fontSize: 12 }}>{item.sales_district}</td>
                  <td className="mono-data">{item.case_qty}</td>
                  <td>
                    <button className="btn btn-danger btn-sm btn-icon" onClick={async () => { await deleteCaseLot(item.id); load() }}>
                      <Trash2 size={11} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && items.length === 0 && <EmptyRow message="No case lot rules." />}
      </div>
    </div>
  )
}

// ─── Shared helpers ───────────────────────────────────────────────────────────

function FormField({ label, value, onChange, type = 'text', flex }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; flex?: number
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: flex ?? 1, minWidth: 120 }}>
      <label style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
        {label}
      </label>
      <input className="input input-sm" type={type} value={value} onChange={e => onChange(e.target.value)} />
    </div>
  )
}

function CustomerTag({ code }: { code: string | null }) {
  const colors: Record<string, string> = {
    RRL: '#6366f1', DMT: '#10b981', BBK: '#f59e0b',
    ZEP: '#8b5cf6', AMZ: '#3b82f6', WMT: '#0ea5e9',
  }
  const color = colors[code || ''] || '#6b7280'
  return (
    <span style={{
      display: 'inline-block', padding: '1px 7px', borderRadius: 4,
      background: `${color}20`, color, fontSize: 11, fontWeight: 700,
      fontFamily: 'var(--font-mono)'
    }}>
      {code || '—'}
    </span>
  )
}

function LoadingRow() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
      <div className="spinner" style={{ width: 24, height: 24 }} />
    </div>
  )
}

function EmptyRow({ message }: { message: string }) {
  return (
    <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
      {message}
    </div>
  )
}