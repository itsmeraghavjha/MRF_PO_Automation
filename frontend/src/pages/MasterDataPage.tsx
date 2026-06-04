import { useEffect, useState } from 'react'
import { Plus, Trash2, RefreshCw, Upload, Edit2, Save, X, CheckCircle2 } from 'lucide-react'
import {
  getCustomers, createCustomer, updateCustomer, deleteCustomer,
  getProducts, createProduct, updateProduct, deleteProduct,
  getPrices, createPrice, updatePrice, deletePrice,
  getLocations, createLocation, updateLocation, deleteLocation,
  getDistricts, createDistrict, updateDistrict, deleteDistrict,
  getInventory,
  getCaseLots, createCaseLot, deleteCaseLot,
  getShSkuSo,
  importAllSheets,
  type CustomerMapping,
  type ProductMapping,
  type PriceMaster,
  type LocationMapping,
  type DistrictMapping,
  type InventoryItem,
  type CaseLot,
  type ShSkuSo,
} from '../services/api'

// ── Tab definition ────────────────────────────────────────────────────────
type Tab = 'customers' | 'products' | 'prices' | 'locations' | 'districts' | 'inventory' | 'caselots' | 'shskuso'

export default function MasterDataPage() {
  const [activeTab, setActiveTab] = useState<Tab>('customers')
  const [importing, setImporting] = useState(false)
  const [importMsg, setImportMsg] = useState<string | null>(null)

  const tabs: { key: Tab; label: string; desc: string }[] = [
    { key: 'customers',  label: 'Customer Mapping', desc: 'Site code → SAP sold-to / ship-to' },
    { key: 'products',   label: 'SKU Mapping',       desc: 'Customer SKU → HFL SKU code' },
    { key: 'prices',     label: 'Price Master',       desc: 'NLC per sold-to + district + SKU' },
    { key: 'locations',  label: 'Location Fallback',  desc: 'Address pattern → SAP ship-to' },
    { key: 'districts',  label: 'District Mapping',   desc: 'Ship-to code → sales district' },
    { key: 'inventory',  label: 'Inventory',          desc: 'Unrestricted stock per SKU + plant' },
    { key: 'caselots',   label: 'Case Lots',          desc: 'Min order qty per cluster + district' },
    { key: 'shskuso',    label: 'SH-SKU-SO',          desc: 'Valid sales office + ship-to + SKU combos' },
  ]

  const handleImportAll = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImporting(true)
    setImportMsg(null)
    try {
      const result = await importAllSheets(file)
      setImportMsg(`Imported ${result.total_imported} records across ${Object.keys(result.sheets).length} sheets`)
    } catch (err: any) {
      setImportMsg(`Import failed: ${err.message}`)
    } finally {
      setImporting(false)
      e.target.value = ''
    }
  }

  return (
    <div style={{ padding: '28px' }} className="animate-fade">
      {/* Header */}
      <div style={{ marginBottom: 20, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: 24, fontWeight: 800, fontFamily: 'var(--font-display)', marginBottom: 4 }}>Master Data</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, margin: 0 }}>
            Reference data used during PO validation
          </p>
        </div>
        <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
          {importing ? <><span className="spinner" style={{ width: 12, height: 12 }} /> Importing…</> : <><Upload size={13} /> Import Master Excel</>}
          <input type="file" accept=".xlsx,.xls" style={{ display: 'none' }} onChange={handleImportAll} disabled={importing} />
        </label>
      </div>

      {importMsg && (
        <div style={{
          background: importMsg.startsWith('Import failed') ? 'rgba(239,68,68,0.08)' : 'rgba(16,185,129,0.08)',
          border: `1px solid ${importMsg.startsWith('Import failed') ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)'}`,
          borderRadius: 8, padding: '10px 14px', marginBottom: 16,
          fontSize: 12, color: importMsg.startsWith('Import failed') ? '#ef4444' : '#10b981',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <CheckCircle2 size={13} />
          {importMsg}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 20, borderBottom: '1px solid var(--border)', overflowX: 'auto' }}>
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              padding: '10px 14px', fontSize: 13, fontWeight: 500,
              color: activeTab === tab.key ? 'var(--text-primary)' : 'var(--text-muted)',
              borderBottom: activeTab === tab.key ? '2px solid var(--accent-amber)' : '2px solid transparent',
              marginBottom: -1, transition: 'all 0.15s', whiteSpace: 'nowrap',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'customers'  && <CustomersTab />}
      {activeTab === 'products'   && <ProductsTab />}
      {activeTab === 'prices'     && <PricesTab />}
      {activeTab === 'locations'  && <LocationsTab />}
      {activeTab === 'districts'  && <DistrictsTab />}
      {activeTab === 'inventory'  && <InventoryTab />}
      {activeTab === 'caselots'   && <CaseLotsTab />}
      {activeTab === 'shskuso'    && <ShSkuSoTab />}
    </div>
  )
}

// ── SHARED HELPERS ────────────────────────────────────────────────────────

function FormField({ label, value, onChange, type = 'text', flex, placeholder }: {
  label: string; value: string; onChange: (v: string) => void
  type?: string; flex?: number; placeholder?: string
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: flex ?? 1, minWidth: 100 }}>
      <label style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
        {label}
      </label>
      <input className="input input-sm" type={type} value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)} />
    </div>
  )
}

function ClusterTag({ code }: { code: string | null }) {
  const colors: Record<string, string> = {
    RRL: '#6366f1', DMT: '#10b981', BBK: '#f59e0b',
    ZEP: '#8b5cf6', AMZ: '#3b82f6', WMT: '#0ea5e9',
  }
  const c = colors[code || ''] || '#6b7280'
  return (
    <span style={{
      display: 'inline-block', padding: '1px 7px', borderRadius: 4,
      background: `${c}20`, color: c,
      fontSize: 11, fontWeight: 700, fontFamily: 'var(--font-mono)',
    }}>
      {code || '—'}
    </span>
  )
}

function LoadingRow() {
  return <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><div className="spinner" style={{ width: 24, height: 24 }} /></div>
}

function EmptyRow({ message }: { message: string }) {
  return <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>{message}</div>
}

function InlineInput({ value, onChange, type = 'text', width = 120 }: {
  value: string; onChange: (v: string) => void; type?: string; width?: number
}) {
  return (
    <input
      className="input input-sm"
      type={type}
      value={value}
      onChange={e => onChange(e.target.value)}
      style={{ width, padding: '3px 8px', fontSize: 12 }}
    />
  )
}

function TabToolbar({ count, label, onRefresh, onAdd, onImport, importAccept }: {
  count: number; label: string; onRefresh: () => void; onAdd?: () => void
  onImport?: (e: React.ChangeEvent<HTMLInputElement>) => void; importAccept?: string
}) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14 }}>
      <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{count} {label}</span>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn btn-ghost btn-sm btn-icon" onClick={onRefresh}><RefreshCw size={13} /></button>
        {onImport && (
          <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
            <Upload size={13} /> Import
            <input type="file" accept={importAccept ?? '.csv,.xlsx,.xls'} style={{ display: 'none' }} onChange={onImport} />
          </label>
        )}
        {onAdd && (
          <button className="btn btn-primary btn-sm" onClick={onAdd}><Plus size={13} /> Add</button>
        )}
      </div>
    </div>
  )
}

// ── CUSTOMERS TAB ─────────────────────────────────────────────────────────

function CustomersTab() {
  const [items, setItems] = useState<CustomerMapping[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [editData, setEditData] = useState<Partial<CustomerMapping>>({})
  const blankForm = { cluster: '', state: '', gst_number: '', full_address: '', site_code: '', sold_to_party: '', ship_to_party_code: '', sales_district: '', sales_office: '', person_responsible: '', email_id: '', contact_number: '' }
  const [form, setForm] = useState(blankForm)

  const load = async () => { setLoading(true); setItems(await getCustomers().catch(() => [])); setLoading(false) }
  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    await createCustomer(form as any)
    setForm(blankForm); setShowForm(false); load()
  }

  const startEdit = (item: CustomerMapping) => {
    setEditId(item.id)
    setEditData({ ...item })
  }

  const handleUpdate = async (id: number) => {
    await updateCustomer(id, editData as any)
    setEditId(null); load()
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return
    const fd = new FormData(); fd.append('file', file)
    await fetch('/api/v1/master-data/customers/import', { method: 'POST', body: fd })
    load(); e.target.value = ''
  }

  const f = (k: keyof typeof blankForm) => (v: string) => setForm(p => ({ ...p, [k]: v }))
  const e = (k: keyof CustomerMapping) => (v: string) => setEditData(p => ({ ...p, [k]: v }))

  return (
    <div>
      <TabToolbar count={items.length} label="customer locations" onRefresh={load} onAdd={() => setShowForm(!showForm)} onImport={handleImport} />

      {showForm && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <FormField label="Cluster *" value={form.cluster} onChange={f('cluster')} placeholder="RRL" />
            <FormField label="State" value={form.state} onChange={f('state')} placeholder="Andhra Pradesh" />
            <FormField label="GST Number" value={form.gst_number} onChange={f('gst_number')} placeholder="37AAACH..." />
            <FormField label="Site Code" value={form.site_code} onChange={f('site_code')} placeholder="2999" />
            <FormField label="Sold-to Party" value={form.sold_to_party} onChange={f('sold_to_party')} placeholder="250029" />
            <FormField label="Ship-to Party" value={form.ship_to_party_code} onChange={f('ship_to_party_code')} placeholder="273774" />
            <FormField label="Sales District" value={form.sales_district} onChange={f('sales_district')} placeholder="APBB01-Bobbili" />
            <FormField label="Sales Office" value={form.sales_office} onChange={f('sales_office')} placeholder="1961-Bobbili" />
            <FormField label="Person Responsible" value={form.person_responsible} onChange={f('person_responsible')} />
            <FormField label="Email" value={form.email_id} onChange={f('email_id')} type="email" />
            <FormField label="Contact" value={form.contact_number} onChange={f('contact_number')} />
            <FormField label="Full Address" value={form.full_address} onChange={f('full_address')} flex={3} />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn btn-primary btn-sm" onClick={handleCreate}>Save</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <LoadingRow /> : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Cluster</th>
                  <th>Site Code</th>
                  <th>Sold-to</th>
                  <th>Ship-to</th>
                  <th>Sales District</th>
                  <th>Sales Office</th>
                  <th>GST</th>
                  <th>State</th>
                  <th>Address</th>
                  <th>Contact Person</th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th style={{ width: 90 }}></th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr key={item.id}>
                    <td>{editId === item.id ? <InlineInput value={String(editData.cluster ?? '')} onChange={e('cluster')} width={70} /> : <ClusterTag code={item.cluster} />}</td>
                    <td className="mono-data">{editId === item.id ? <InlineInput value={String(editData.site_code ?? '')} onChange={e('site_code')} /> : (item.site_code || '—')}</td>
                    <td className="mono-data">{editId === item.id ? <InlineInput value={String(editData.sold_to_party ?? '')} onChange={e('sold_to_party')} /> : (item.sold_to_party || '—')}</td>
                    <td className="mono-data">{editId === item.id ? <InlineInput value={String(editData.ship_to_party_code ?? '')} onChange={e('ship_to_party_code')} /> : (item.ship_to_party_code || '—')}</td>
                    <td style={{ fontSize: 12 }}>{editId === item.id ? <InlineInput value={String(editData.sales_district ?? '')} onChange={e('sales_district')} width={150} /> : (item.sales_district || '—')}</td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{editId === item.id ? <InlineInput value={String(editData.sales_office ?? '')} onChange={e('sales_office')} width={150} /> : (item.sales_office || '—')}</td>
                    <td className="mono-data" style={{ fontSize: 11 }}>{editId === item.id ? <InlineInput value={String(editData.gst_number ?? '')} onChange={e('gst_number')} /> : (item.gst_number || '—')}</td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{editId === item.id ? <InlineInput value={String(editData.state ?? '')} onChange={e('state')} width={100} /> : (item.state || '—')}</td>
                    <td style={{ fontSize: 11, maxWidth: 150 }} title={item.full_address || ''}>
                      {editId === item.id ? (
                        <InlineInput value={String(editData.full_address ?? '')} onChange={e('full_address')} width={140} />
                      ) : (
                        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.full_address || '—'}</div>
                      )}
                    </td>
                    <td style={{ fontSize: 11 }}>{editId === item.id ? <InlineInput value={String(editData.person_responsible ?? '')} onChange={e('person_responsible')} width={100} /> : (item.person_responsible || '—')}</td>
                    <td style={{ fontSize: 11 }}>{editId === item.id ? <InlineInput value={String(editData.email_id ?? '')} onChange={e('email_id')} width={120} /> : (item.email_id || '—')}</td>
                    <td style={{ fontSize: 11 }}>{editId === item.id ? <InlineInput value={String(editData.contact_number ?? '')} onChange={e('contact_number')} width={90} /> : (item.contact_number || '—')}</td>

                    <td></td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {editId === item.id ? (
                          <>
                            <button className="btn btn-success btn-sm btn-icon" onClick={() => handleUpdate(item.id)}><Save size={11} /></button>
                            <button className="btn btn-ghost btn-sm btn-icon" onClick={() => setEditId(null)}><X size={11} /></button>
                          </>
                        ) : (
                          <>
                            <button className="btn btn-ghost btn-sm btn-icon" onClick={() => startEdit(item)}><Edit2 size={11} /></button>
                            <button className="btn btn-danger btn-sm btn-icon" onClick={async () => { await deleteCustomer(item.id); load() }}><Trash2 size={11} /></button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!loading && items.length === 0 && <EmptyRow message="No customer mappings. Add one above or import the Customer Mapping sheet." />}
      </div>
    </div>
  )
}

// ── PRODUCTS TAB (SKU Mapping) ────────────────────────────────────────────

function ProductsTab() {
  const [items, setItems] = useState<ProductMapping[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [editData, setEditData] = useState<Partial<ProductMapping>>({})
  const blank = { sold_to_party: '', customer_sku: '', customer_product_text: '', hfl_sku_code: '', description: '', uom: '', division: '', taxable: true }
  const [form, setForm] = useState<typeof blank>(blank)

  const load = async () => { setLoading(true); setItems(await getProducts().catch(() => [])); setLoading(false) }
  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    await createProduct(form as any); setForm(blank); setShowForm(false); load()
  }

  const startEdit = (item: ProductMapping) => { setEditId(item.id); setEditData({ ...item }) }

  const handleUpdate = async (id: number) => {
    await updateProduct(id, editData as any); setEditId(null); load()
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return
    const fd = new FormData(); fd.append('file', file)
    await fetch('/api/v1/master-data/products/import', { method: 'POST', body: fd })
    load(); e.target.value = ''
  }

  const f = (k: keyof typeof blank) => (v: string) => setForm(p => ({ ...p, [k]: v }))
  const ed = (k: keyof ProductMapping) => (v: string) => setEditData(p => ({ ...p, [k]: v }))

  return (
    <div>
      <TabToolbar count={items.length} label="SKU mappings" onRefresh={load} onAdd={() => setShowForm(!showForm)} onImport={handleImport} />

      {showForm && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <FormField label="Sold-to Party *" value={form.sold_to_party} onChange={f('sold_to_party')} placeholder="250029" />
            <FormField label="Customer SKU" value={form.customer_sku} onChange={f('customer_sku')} placeholder="590000720" />
            <FormField label="Customer Product Text" value={form.customer_product_text} onChange={f('customer_product_text')} flex={2} />
            <FormField label="HFL SKU Code *" value={form.hfl_sku_code} onChange={f('hfl_sku_code')} placeholder="10017" />
            <FormField label="Description" value={form.description} onChange={f('description')} />
            <FormField label="UOM" value={form.uom} onChange={f('uom')} placeholder="CS" />
            <FormField label="Division" value={form.division} onChange={f('division')} />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer' }}>
              <input type="checkbox" checked={form.taxable} onChange={e => setForm(p => ({ ...p, taxable: e.target.checked }))} />
              Taxable
            </label>
            <button className="btn btn-primary btn-sm" onClick={handleCreate}>Save</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <LoadingRow /> : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Sold-to</th>
                  <th>Customer SKU</th>
                  <th>Customer Product Text</th>
                  <th>HFL SKU Code</th>
                  <th>Description</th>
                  <th>UOM</th>
                  <th>Division</th>
                  <th>Tax</th>
                  <th style={{ width: 90 }}></th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr key={item.id}>
                    <td className="mono-data">{editId === item.id ? <InlineInput value={String(editData.sold_to_party ?? '')} onChange={ed('sold_to_party')} /> : item.sold_to_party}</td>
                    <td className="mono-data" style={{ fontSize: 11 }}>{editId === item.id ? <InlineInput value={String(editData.customer_sku ?? '')} onChange={ed('customer_sku')} /> : (item.customer_sku || '—')}</td>
                    <td style={{ fontSize: 12, maxWidth: 200 }}>
                      {editId === item.id ? <InlineInput value={String(editData.customer_product_text ?? '')} onChange={ed('customer_product_text')} width={190} /> : <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>{item.customer_product_text || '—'}</span>}
                    </td>
                    <td className="mono-data" style={{ color: 'var(--accent-amber)' }}>{editId === item.id ? <InlineInput value={String(editData.hfl_sku_code ?? '')} onChange={ed('hfl_sku_code')} /> : item.hfl_sku_code}</td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{editId === item.id ? <InlineInput value={String(editData.description ?? '')} onChange={ed('description')} /> : (item.description || '—')}</td>
                    <td style={{ fontSize: 12 }}>{editId === item.id ? <InlineInput value={String(editData.uom ?? '')} onChange={ed('uom')} width={60} /> : (item.uom || '—')}</td>
                    <td style={{ fontSize: 12 }}>{editId === item.id ? <InlineInput value={String(editData.division ?? '')} onChange={ed('division')} width={80} /> : (item.division || '—')}</td>
                    <td>
                      {editId === item.id
                        ? <input type="checkbox" checked={!!editData.taxable} onChange={ev => setEditData(p => ({ ...p, taxable: ev.target.checked }))} />
                        : <span style={{ fontSize: 11, color: item.taxable ? '#10b981' : 'var(--text-muted)' }}>{item.taxable ? 'Yes' : 'No'}</span>
                      }
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {editId === item.id ? (
                          <><button className="btn btn-success btn-sm btn-icon" onClick={() => handleUpdate(item.id)}><Save size={11} /></button><button className="btn btn-ghost btn-sm btn-icon" onClick={() => setEditId(null)}><X size={11} /></button></>
                        ) : (
                          <><button className="btn btn-ghost btn-sm btn-icon" onClick={() => startEdit(item)}><Edit2 size={11} /></button><button className="btn btn-danger btn-sm btn-icon" onClick={async () => { await deleteProduct(item.id); load() }}><Trash2 size={11} /></button></>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!loading && items.length === 0 && <EmptyRow message="No SKU mappings. Add one above or import the SKU Mapping sheet." />}
      </div>
    </div>
  )
}

// ── PRICES TAB ────────────────────────────────────────────────────────────

function PricesTab() {
  const [items, setItems] = useState<PriceMaster[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [editData, setEditData] = useState<Partial<PriceMaster>>({})
  const blank = { region: '', sales_district: '', sold_to_party: '', sku_code: '', mrp: '', margin: '', offer: '', nlc: '', effective_from: '', effective_to: '' }
  const [form, setForm] = useState(blank)

  const load = async () => { setLoading(true); setItems(await getPrices().catch(() => [])); setLoading(false) }
  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    await createPrice({
      region: form.region || null,
      sales_district: form.sales_district,
      sold_to_party: form.sold_to_party,
      sku_code: form.sku_code,
      mrp: form.mrp ? Number(form.mrp) : null,
      margin: form.margin ? Number(form.margin) : null,
      offer: form.offer ? Number(form.offer) : null,
      nlc: Number(form.nlc),
      effective_from: form.effective_from || null,
      effective_to: form.effective_to || null,
    })
    setForm(blank); setShowForm(false); load()
  }

  const startEdit = (item: PriceMaster) => { setEditId(item.id); setEditData({ ...item }) }

  const handleUpdate = async (id: number) => {
    await updatePrice(id, editData as any); setEditId(null); load()
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return
    const fd = new FormData(); fd.append('file', file)
    await fetch('/api/v1/master-data/prices/import', { method: 'POST', body: fd })
    load(); e.target.value = ''
  }

  const f = (k: keyof typeof blank) => (v: string) => setForm(p => ({ ...p, [k]: v }))
  const ed = (k: keyof PriceMaster) => (v: string) => setEditData(p => ({ ...p, [k]: v as any }))

  return (
    <div>
      <TabToolbar count={items.length} label="price records" onRefresh={load} onAdd={() => setShowForm(!showForm)} onImport={handleImport} />

      {showForm && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <FormField label="Region" value={form.region} onChange={f('region')} placeholder="South" />
            <FormField label="Sales District *" value={form.sales_district} onChange={f('sales_district')} placeholder="APBB01-Bobbili" />
            <FormField label="Sold-to Party *" value={form.sold_to_party} onChange={f('sold_to_party')} placeholder="250029" />
            <FormField label="SKU Code *" value={form.sku_code} onChange={f('sku_code')} placeholder="70004" />
            <FormField label="MRP (₹)" value={form.mrp} onChange={f('mrp')} type="number" />
            <FormField label="Margin %" value={form.margin} onChange={f('margin')} type="number" />
            <FormField label="Offer" value={form.offer} onChange={f('offer')} type="number" />
            <FormField label="NLC (₹) *" value={form.nlc} onChange={f('nlc')} type="number" />
            <FormField label="Valid From" value={form.effective_from} onChange={f('effective_from')} placeholder="01.05.2026" />
            <FormField label="Valid To" value={form.effective_to} onChange={f('effective_to')} placeholder="31.05.2026" />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn btn-primary btn-sm" onClick={handleCreate}>Save</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <LoadingRow /> : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Region</th>
                  <th>Sales District</th>
                  <th>Sold-to</th>
                  <th>SKU Code</th>
                  <th>MRP</th>
                  <th>NLC</th>
                  <th>Margin %</th>
                  <th>Offer</th>
                  <th>Valid From</th>
                  <th>Valid To</th>
                  <th style={{ width: 90 }}></th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr key={item.id}>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{editId === item.id ? <InlineInput value={String(editData.region ?? '')} onChange={ed('region')} width={80} /> : (item.region || '—')}</td>
                    <td style={{ fontSize: 12 }}>{editId === item.id ? <InlineInput value={String(editData.sales_district ?? '')} onChange={ed('sales_district')} width={150} /> : item.sales_district}</td>
                    <td className="mono-data">{editId === item.id ? <InlineInput value={String(editData.sold_to_party ?? '')} onChange={ed('sold_to_party')} /> : item.sold_to_party}</td>
                    <td className="mono-data" style={{ color: 'var(--accent-amber)' }}>{editId === item.id ? <InlineInput value={String(editData.sku_code ?? '')} onChange={ed('sku_code')} /> : item.sku_code}</td>
                    <td className="mono-data" style={{ fontSize: 12 }}>{editId === item.id ? <InlineInput value={String(editData.mrp ?? '')} onChange={ed('mrp')} type="number" width={80} /> : (item.mrp != null ? `₹${item.mrp}` : '—')}</td>
                    <td className="mono-data" style={{ color: '#10b981', fontWeight: 600 }}>{editId === item.id ? <InlineInput value={String(editData.nlc ?? '')} onChange={ed('nlc')} type="number" width={80} /> : `₹${item.nlc}`}</td>
                    <td className="mono-data" style={{ fontSize: 12 }}>{editId === item.id ? <InlineInput value={String(editData.margin ?? '')} onChange={ed('margin')} type="number" width={70} /> : (item.margin != null ? `${item.margin}%` : '—')}</td>
                    
                    <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>{editId === item.id ? <InlineInput value={String(editData.effective_from ?? '')} onChange={ed('effective_from')} /> : (item.effective_from || '—')}</td>
                    <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>{editId === item.id ? <InlineInput value={String(editData.effective_to ?? '')} onChange={ed('effective_to')} /> : (item.effective_to || '—')}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {editId === item.id ? (
                          <><button className="btn btn-success btn-sm btn-icon" onClick={() => handleUpdate(item.id)}><Save size={11} /></button><button className="btn btn-ghost btn-sm btn-icon" onClick={() => setEditId(null)}><X size={11} /></button></>
                        ) : (
                          <><button className="btn btn-ghost btn-sm btn-icon" onClick={() => startEdit(item)}><Edit2 size={11} /></button><button className="btn btn-danger btn-sm btn-icon" onClick={async () => { await deletePrice(item.id); load() }}><Trash2 size={11} /></button></>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!loading && items.length === 0 && <EmptyRow message="No price records. Add one above or import the Pricing Mapping sheet." />}
      </div>
    </div>
  )
}

// ── LOCATIONS TAB ─────────────────────────────────────────────────────────

function LocationsTab() {
  const [items, setItems] = useState<LocationMapping[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [editData, setEditData] = useState<Partial<LocationMapping>>({})
  const blank = { cluster: '', address_pattern: '', sap_ship_to_code: '', sales_district: '', city: '', state: '' }
  const [form, setForm] = useState(blank)

  const load = async () => { setLoading(true); setItems(await getLocations().catch(() => [])); setLoading(false) }
  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    await createLocation(form as any); setForm(blank); setShowForm(false); load()
  }

  const startEdit = (item: LocationMapping) => { setEditId(item.id); setEditData({ ...item }) }

  const handleUpdate = async (id: number) => {
    await updateLocation(id, editData as any); setEditId(null); load()
  }

  const f = (k: keyof typeof blank) => (v: string) => setForm(p => ({ ...p, [k]: v }))
  const ed = (k: keyof LocationMapping) => (v: string) => setEditData(p => ({ ...p, [k]: v }))

  return (
    <div>
      <div style={{ background: 'rgba(79,142,247,0.06)', border: '1px solid rgba(79,142,247,0.15)', borderRadius: 8, padding: '10px 14px', marginBottom: 14, fontSize: 12, color: 'var(--text-secondary)' }}>
        Fallback lookup when site code / sold-to party matching (CustomerMapping) fails. Uses fuzzy address pattern matching.
      </div>

      <TabToolbar count={items.length} label="location patterns" onRefresh={load} onAdd={() => setShowForm(!showForm)} />

      {showForm && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <FormField label="Cluster *" value={form.cluster} onChange={f('cluster')} placeholder="RRL" />
            <FormField label="Address Pattern *" value={form.address_pattern} onChange={f('address_pattern')} flex={3} placeholder="Jubilee Hills, Hyderabad" />
            <FormField label="SAP Ship-to Code *" value={form.sap_ship_to_code} onChange={f('sap_ship_to_code')} placeholder="273774" />
            <FormField label="Sales District" value={form.sales_district} onChange={f('sales_district')} />
            <FormField label="City" value={form.city} onChange={f('city')} />
            <FormField label="State" value={form.state} onChange={f('state')} />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn btn-primary btn-sm" onClick={handleCreate}>Save</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <LoadingRow /> : (
          <table className="data-table">
            <thead>
              <tr><th>Cluster</th><th>Address Pattern</th><th>SAP Ship-to</th><th>Sales District</th><th>City</th><th>State</th><th style={{ width: 90 }}></th></tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id}>
                  <td>{editId === item.id ? <InlineInput value={String(editData.cluster ?? '')} onChange={ed('cluster')} width={70} /> : <ClusterTag code={item.cluster} />}</td>
                  <td style={{ fontSize: 11, maxWidth: 200 }}>{editId === item.id ? <InlineInput value={String(editData.address_pattern ?? '')} onChange={ed('address_pattern')} width={190} /> : <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>{item.address_pattern}</span>}</td>
                  <td className="mono-data">{editId === item.id ? <InlineInput value={String(editData.sap_ship_to_code ?? '')} onChange={ed('sap_ship_to_code')} /> : item.sap_ship_to_code}</td>
                  <td style={{ fontSize: 12 }}>{editId === item.id ? <InlineInput value={String(editData.sales_district ?? '')} onChange={ed('sales_district')} width={150} /> : (item.sales_district || '—')}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{editId === item.id ? <InlineInput value={String(editData.city ?? '')} onChange={ed('city')} width={90} /> : (item.city || '—')}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{editId === item.id ? <InlineInput value={String(editData.state ?? '')} onChange={ed('state')} width={90} /> : (item.state || '—')}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {editId === item.id ? (
                        <><button className="btn btn-success btn-sm btn-icon" onClick={() => handleUpdate(item.id)}><Save size={11} /></button><button className="btn btn-ghost btn-sm btn-icon" onClick={() => setEditId(null)}><X size={11} /></button></>
                      ) : (
                        <><button className="btn btn-ghost btn-sm btn-icon" onClick={() => startEdit(item)}><Edit2 size={11} /></button><button className="btn btn-danger btn-sm btn-icon" onClick={async () => { await deleteLocation(item.id); load() }}><Trash2 size={11} /></button></>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && items.length === 0 && <EmptyRow message="No location patterns." />}
      </div>
    </div>
  )
}

// ── DISTRICTS TAB ─────────────────────────────────────────────────────────

function DistrictsTab() {
  const [items, setItems] = useState<DistrictMapping[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [editData, setEditData] = useState<Partial<DistrictMapping>>({})
  const blank = { ship_to_code: '', sales_district: '', cluster: '' }
  const [form, setForm] = useState(blank)

  const load = async () => { setLoading(true); setItems(await getDistricts().catch(() => [])); setLoading(false) }
  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    await createDistrict({ ship_to_code: form.ship_to_code, sales_district: form.sales_district, cluster: form.cluster || null })
    setForm(blank); setShowForm(false); load()
  }

  const startEdit = (item: DistrictMapping) => { setEditId(item.id); setEditData({ ...item }) }

  const handleUpdate = async (id: number) => {
    await updateDistrict(id, editData as any); setEditId(null); load()
  }

  const f = (k: keyof typeof blank) => (v: string) => setForm(p => ({ ...p, [k]: v }))
  const ed = (k: keyof DistrictMapping) => (v: string) => setEditData(p => ({ ...p, [k]: v }))

  return (
    <div>
      <div style={{ background: 'rgba(79,142,247,0.06)', border: '1px solid rgba(79,142,247,0.15)', borderRadius: 8, padding: '10px 14px', marginBottom: 14, fontSize: 12, color: 'var(--text-secondary)' }}>
        Maps a SAP Ship-to Code → Sales District. Required for Case Lot validation (VR-04) when CustomerMapping doesn't carry the district.
      </div>

      <TabToolbar count={items.length} label="district mappings" onRefresh={load} onAdd={() => setShowForm(!showForm)} />

      {showForm && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <FormField label="Ship-to Code *" value={form.ship_to_code} onChange={f('ship_to_code')} placeholder="273774" />
            <FormField label="Sales District *" value={form.sales_district} onChange={f('sales_district')} placeholder="APBB01-Bobbili" flex={2} />
            <FormField label="Cluster" value={form.cluster} onChange={f('cluster')} placeholder="RRL" />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn btn-primary btn-sm" onClick={handleCreate}>Save</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <LoadingRow /> : (
          <table className="data-table">
            <thead><tr><th>Ship-to Code</th><th>Sales District</th><th>Cluster</th><th style={{ width: 90 }}></th></tr></thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id}>
                  <td className="mono-data">{editId === item.id ? <InlineInput value={String(editData.ship_to_code ?? '')} onChange={ed('ship_to_code')} /> : item.ship_to_code}</td>
                  <td style={{ fontSize: 12 }}>{editId === item.id ? <InlineInput value={String(editData.sales_district ?? '')} onChange={ed('sales_district')} width={200} /> : item.sales_district}</td>
                  <td>{editId === item.id ? <InlineInput value={String(editData.cluster ?? '')} onChange={ed('cluster')} width={80} /> : <ClusterTag code={item.cluster} />}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {editId === item.id ? (
                        <><button className="btn btn-success btn-sm btn-icon" onClick={() => handleUpdate(item.id)}><Save size={11} /></button><button className="btn btn-ghost btn-sm btn-icon" onClick={() => setEditId(null)}><X size={11} /></button></>
                      ) : (
                        <><button className="btn btn-ghost btn-sm btn-icon" onClick={() => startEdit(item)}><Edit2 size={11} /></button><button className="btn btn-danger btn-sm btn-icon" onClick={async () => { await deleteDistrict(item.id); load() }}><Trash2 size={11} /></button></>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && items.length === 0 && <EmptyRow message="No district mappings. Add one above." />}
      </div>
    </div>
  )
}

// ── INVENTORY TAB ─────────────────────────────────────────────────────────

function InventoryTab() {
  const [items, setItems] = useState<InventoryItem[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => { setLoading(true); setItems(await getInventory().catch(() => [])); setLoading(false) }
  useEffect(() => { load() }, [])

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return
    const fd = new FormData(); fd.append('file', file)
    await fetch('/api/v1/master-data/inventory/import', { method: 'POST', body: fd })
    load(); e.target.value = ''
  }

  return (
    <div>
      <TabToolbar count={items.length} label="stock records" onRefresh={load} onImport={handleImport} />

      <div style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.15)', borderRadius: 8, padding: '10px 14px', marginBottom: 14, fontSize: 12, color: 'var(--text-secondary)' }}>
        Full delete + re-import on each upload. Required columns: <code style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>hfl_sku_code, plant_code, unrestricted_stock</code>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <LoadingRow /> : (
          <table className="data-table">
            <thead><tr><th>HFL SKU Code</th><th>Plant</th><th>Unrestricted Stock</th><th>Last Refreshed</th></tr></thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id}>
                  <td className="mono-data" style={{ color: 'var(--accent-amber)' }}>{item.hfl_sku_code}</td>
                  <td className="mono-data">{item.plant_code}</td>
                  <td>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: item.unrestricted_stock > 100 ? '#10b981' : item.unrestricted_stock > 0 ? '#f59e0b' : '#ef4444' }}>
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

// ── CASE LOTS TAB ─────────────────────────────────────────────────────────

function CaseLotsTab() {
  const [items, setItems] = useState<CaseLot[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const blank = { cluster: '', sales_district: '', sku_code: '', case_qty: '' }
  const [form, setForm] = useState(blank)

  const load = async () => { setLoading(true); setItems(await getCaseLots().catch(() => [])); setLoading(false) }
  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    await createCaseLot({ cluster: form.cluster, sales_district: form.sales_district, sku_code: form.sku_code, case_qty: Number(form.case_qty) })
    setForm(blank); setShowForm(false); load()
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return
    const fd = new FormData(); fd.append('file', file)
    await fetch('/api/v1/master-data/case-lots/import', { method: 'POST', body: fd })
    load(); e.target.value = ''
  }

  const f = (k: keyof typeof blank) => (v: string) => setForm(p => ({ ...p, [k]: v }))

  return (
    <div>
      <TabToolbar count={items.length} label="case lot rules" onRefresh={load} onAdd={() => setShowForm(!showForm)} onImport={handleImport} />

      {showForm && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <FormField label="Cluster *" value={form.cluster} onChange={f('cluster')} placeholder="RRL" />
            <FormField label="Sales District *" value={form.sales_district} onChange={f('sales_district')} placeholder="APBB01-Bobbili" flex={2} />
            <FormField label="SKU Code *" value={form.sku_code} onChange={f('sku_code')} placeholder="70004" />
            <FormField label="Case Qty *" value={form.case_qty} onChange={f('case_qty')} type="number" placeholder="12" />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn btn-primary btn-sm" onClick={handleCreate}>Save</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <LoadingRow /> : (
          <table className="data-table">
            <thead><tr><th>Cluster</th><th>Sales District</th><th>SKU Code</th><th>Case Qty</th><th style={{ width: 60 }}></th></tr></thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id}>
                  <td><ClusterTag code={item.cluster} /></td>
                  <td style={{ fontSize: 12 }}>{item.sales_district}</td>
                  <td className="mono-data" style={{ color: 'var(--accent-amber)' }}>{item.sku_code}</td>
                  <td className="mono-data">{item.case_qty}</td>
                  <td>
                    <button className="btn btn-danger btn-sm btn-icon" onClick={async () => { await deleteCaseLot(item.id); load() }}><Trash2 size={11} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && items.length === 0 && <EmptyRow message="No case lot rules. Add one above or import the CaseLot sheet." />}
      </div>
    </div>
  )
}

// ── SH-SKU-SO TAB ─────────────────────────────────────────────────────────

function ShSkuSoTab() {
  const [items, setItems] = useState<ShSkuSo[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => { setLoading(true); setItems(await getShSkuSo().catch(() => [])); setLoading(false) }
  useEffect(() => { load() }, [])

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return
    const fd = new FormData(); fd.append('file', file)
    await fetch('/api/v1/master-data/sh-sku-so/import', { method: 'POST', body: fd })
    load(); e.target.value = ''
  }

  return (
    <div>
      <div style={{ background: 'rgba(79,142,247,0.06)', border: '1px solid rgba(79,142,247,0.15)', borderRadius: 8, padding: '10px 14px', marginBottom: 14, fontSize: 12, color: 'var(--text-secondary)' }}>
        Valid combinations of Sales Office + Ship-to + HFL SKU. Bulk import only (read-only in UI). Expected columns: <code style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>Sales Office, HFL Ship to code, HFL SKU Code, Material Description</code>
      </div>

      <TabToolbar count={items.length} label="SH-SKU-SO combos" onRefresh={load} onImport={handleImport} />

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <LoadingRow /> : (
          <table className="data-table">
            <thead><tr><th>Sales Office</th><th>Ship-to Code</th><th>HFL SKU Code</th><th>Material Description</th></tr></thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id}>
                  <td style={{ fontSize: 12 }}>{item.sales_office}</td>
                  <td className="mono-data">{item.ship_to_code}</td>
                  <td className="mono-data" style={{ color: 'var(--accent-amber)' }}>{item.hfl_sku_code}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{item.material_description || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && items.length === 0 && <EmptyRow message="No SH-SKU-SO data. Import the SH-SKU-SO sheet." />}
      </div>
    </div>
  )
}