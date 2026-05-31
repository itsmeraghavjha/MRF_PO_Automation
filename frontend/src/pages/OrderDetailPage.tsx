import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, RefreshCw, Send, CheckCircle2, AlertTriangle,
  Clock, FileText, Edit2, Save, X, ChevronRight, ExternalLink
} from 'lucide-react'
import {
  getOrder, revalidateOrder, pushToSAP, updateLineItem,
  type OrderDetail, type LineItem
} from '../services/api'
import { StatusBadge, formatCurrency, formatDate, formatDateTime, CustomerChip } from '../components/shared/StatusBadge'

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [order, setOrder] = useState<OrderDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [showPdf, setShowPdf] = useState(true)

  const load = async () => {
    if (!id) return
    setLoading(true)
    try {
      const o = await getOrder(Number(id))
      setOrder(o)
      if (o.drive_link) {
        const filename = o.drive_link.split('/').pop()
        setPdfUrl(`/pdfs/${filename}`)
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  const handleRevalidate = async () => {
    if (!order) return
    setActionLoading(true)
    setError(null)
    try {
      await revalidateOrder(order.id)
      await load()
      setSuccessMsg('Re-validation complete')
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleSAPPush = async () => {
    if (!order) return
    setActionLoading(true)
    setError(null)
    try {
      const result = await pushToSAP(order.id)
      await load()
      setSuccessMsg(`SAP CSV generated: ${result.csv_filename}`)
      setTimeout(() => setSuccessMsg(null), 5000)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleLineItemSaved = async () => {
    await load()
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <div className="spinner" style={{ width: 32, height: 32 }} />
      </div>
    )
  }

  if (!order) {
    return <div style={{ padding: 28 }}><div style={{ color: 'var(--status-failed)' }}>Order not found.</div></div>
  }

  const canPushSAP = order.status === 'VALIDATED'
  const canRevalidate = ['VALIDATION_FAILED', 'VALIDATED', 'AWAITING_DELIVERY_DATE'].includes(order.status)
  const hasPdf = !!pdfUrl && pdfUrl.toLowerCase().endsWith('.pdf')

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* ── LEFT PANEL: Order Data ── */}
      <div style={{
        flex: showPdf && hasPdf ? '0 0 55%' : '1 1 100%',
        overflowY: 'auto',
        padding: '24px',
        transition: 'flex 0.3s ease',
        borderRight: showPdf && hasPdf ? '1px solid var(--border)' : 'none',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
          <button className="btn btn-ghost btn-sm btn-icon" onClick={() => navigate('/orders')}>
            <ArrowLeft size={15} />
          </button>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <h2 style={{ fontSize: 18, fontWeight: 800, fontFamily: 'var(--font-display)', margin: 0 }}>
                {order.po_number}
              </h2>
              <StatusBadge status={order.status} />
              {order.is_update && (
                <span className="badge" style={{ background: 'rgba(226,168,75,0.12)', color: '#e2a84b' }}>REVISED</span>
              )}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              {formatDateTime(order.created_at)} · {order.email_sender}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
            {hasPdf && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setShowPdf(s => !s)}
                style={{ fontSize: 11 }}
              >
                <FileText size={12} />
                {showPdf ? 'Hide PDF' : 'View PDF'}
              </button>
            )}
            <button className="btn btn-ghost btn-sm btn-icon" onClick={load} disabled={actionLoading}>
              <RefreshCw size={13} />
            </button>
            {canRevalidate && (
              <button className="btn btn-secondary btn-sm" onClick={handleRevalidate} disabled={actionLoading}>
                <RefreshCw size={13} /> Re-validate
              </button>
            )}
            {canPushSAP && (
              <button className="btn btn-primary btn-sm" onClick={handleSAPPush} disabled={actionLoading}>
                <Send size={13} /> Push to SAP
              </button>
            )}
          </div>
        </div>

        {/* Alerts */}
        {error && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '9px 12px', marginBottom: 12, color: '#ef4444', fontSize: 12 }}>
            {error}
          </div>
        )}
        {successMsg && (
          <div style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 8, padding: '9px 12px', marginBottom: 12, color: '#10b981', fontSize: 12 }}>
            <CheckCircle2 size={12} style={{ display: 'inline', marginRight: 5 }} />
            {successMsg}
          </div>
        )}
        {order.rejection_summary && (
          <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: '9px 12px', marginBottom: 12, fontSize: 12 }}>
            <AlertTriangle size={12} style={{ display: 'inline', marginRight: 5, color: '#ef4444' }} />
            <span style={{ color: '#ef4444', fontWeight: 600 }}>Failures: </span>
            <span style={{ color: 'var(--text-secondary)' }}>{order.rejection_summary}</span>
          </div>
        )}

        {/* Meta Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
          <div className="card" style={{ padding: 14 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>Order Info</div>
            <MetaRow label="Customer"><CustomerChip code={order.customer_code} name={order.customer_name} /></MetaRow>
            <MetaRow label="PO Date">{order.po_date || '—'}</MetaRow>
            <MetaRow label="Delivery">
              {order.delivery_date
                ? <span style={{ color: '#10b981' }}>{formatDate(order.delivery_date)}</span>
                : <span style={{ color: '#f59e0b', display: 'flex', alignItems: 'center', gap: 4 }}><Clock size={10} /> Not set</span>
              }
            </MetaRow>
            <MetaRow label="Total Value">{formatCurrency(order.total_value)}</MetaRow>
            <MetaRow label="Lines">{order.line_item_count} ({order.failed_line_count} failed)</MetaRow>
          </div>
          <div className="card" style={{ padding: 14 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>Delivery & Legal</div>
            <MetaRow label="Ship To Code">{order.ship_to_code || <span style={{ color: '#ef4444' }}>Not mapped</span>}</MetaRow>
            <MetaRow label="Ship To">{order.ship_to_address || '—'}</MetaRow>
            <MetaRow label="GSTIN">
              {order.vendor_gstin
                ? <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>{order.vendor_gstin}</span>
                : <span style={{ color: '#ef4444' }}>Missing</span>
              }
            </MetaRow>
            {pdfUrl && (
              <MetaRow label="Attachment">
                <a href={pdfUrl} target="_blank" rel="noreferrer"
                  style={{ color: 'var(--accent-blue)', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <ExternalLink size={10} /> Open file
                </a>
              </MetaRow>
            )}
          </div>
        </div>

        {/* Line Items */}
        <LineItemsTable
          order={order}
          onSaved={handleLineItemSaved}
          canEdit={order.status !== 'SAP_SUCCESS'}
        />

        {/* Audit Log */}
        <div className="card" style={{ marginTop: 14, padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-display)', margin: 0 }}>Audit Trail</h3>
          </div>
          <div style={{ padding: '4px 0', maxHeight: 200, overflowY: 'auto' }}>
            {order.audit_logs.length === 0 && (
              <div style={{ padding: '20px', color: 'var(--text-muted)', fontSize: 12, textAlign: 'center' }}>No audit events yet</div>
            )}
            {order.audit_logs.map(log => (
              <div key={log.id} style={{ display: 'flex', gap: 10, padding: '8px 16px', borderBottom: '1px solid var(--border)', alignItems: 'flex-start' }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-blue)', marginTop: 5, flexShrink: 0 }} />
                <div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{log.description}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>
                    {log.event_type} · {log.performed_by} · {formatDateTime(log.created_at)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── RIGHT PANEL: PDF Viewer ── */}
      {showPdf && hasPdf && (
        <div style={{ flex: '0 0 45%', display: 'flex', flexDirection: 'column', background: '#1a2332', borderLeft: '1px solid var(--border)' }}>
          {/* PDF Toolbar */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 14px', borderBottom: '1px solid var(--border)',
            background: 'var(--bg-surface)', flexShrink: 0
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <FileText size={13} color="var(--accent-amber)" />
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
                Original PO Document
              </span>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <a href={pdfUrl!} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm" style={{ fontSize: 11 }}>
                <ExternalLink size={11} /> Open
              </a>
              <button className="btn btn-ghost btn-sm btn-icon" onClick={() => setShowPdf(false)}>
                <X size={13} />
              </button>
            </div>
          </div>
          {/* iframe */}
          <iframe
            src={pdfUrl!}
            style={{ flex: 1, border: 'none', width: '100%' }}
            title="PO Document"
          />
        </div>
      )}
    </div>
  )
}

// ── Line Items Table with live grand total ────────────────────────────────

function LineItemsTable({ order, onSaved, canEdit }: {
  order: OrderDetail; onSaved: () => void; canEdit: boolean
}) {
  const [lineItems, setLineItems] = useState(order.line_items)

  useEffect(() => {
    setLineItems(order.line_items)
  }, [order.line_items])

  const updateLocalItem = (id: number, changes: Partial<LineItem>) => {
    setLineItems(prev => prev.map(item =>
      item.id === id ? { ...item, ...changes } : item
    ))
  }

  // Live grand total from local state
  const liveTotal = lineItems.reduce((sum, item) => {
    const lineTotal = (item.qty ?? 0) * (item.unit_price ?? 0)
    return sum + lineTotal
  }, 0)

  const originalTotal = order.total_value ?? 0
  const totalChanged = Math.abs(liveTotal - originalTotal) > 0.01

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-display)', margin: 0 }}>Line Items</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {totalChanged && (
            <span style={{ fontSize: 11, color: '#f59e0b' }}>
              Edited total: {formatCurrency(liveTotal)}
            </span>
          )}
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: totalChanged ? '#f59e0b' : '#10b981' }}>
            {formatCurrency(totalChanged ? liveTotal : originalTotal)}
          </span>
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Material Code</th>
              <th>Description</th>
              <th>UOM</th>
              <th>Qty</th>
              <th>Unit Price</th>
              <th>Tax %</th>
              <th>Line Total</th>
              <th>Status</th>
              {canEdit && <th></th>}
            </tr>
          </thead>
          <tbody>
            {lineItems.map(item => (
              <LineItemRow
                key={item.id}
                item={item}
                orderId={order.id}
                onSaved={onSaved}
                onLocalChange={updateLocalItem}
                canEdit={canEdit}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Single Line Item Row ──────────────────────────────────────────────────

function LineItemRow({ item, orderId, onSaved, onLocalChange, canEdit }: {
  item: LineItem
  orderId: number
  onSaved: () => void
  onLocalChange: (id: number, changes: Partial<LineItem>) => void
  canEdit: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [qty, setQty] = useState(String(item.qty ?? ''))
  const [price, setPrice] = useState(String(item.unit_price ?? ''))
  const [saving, setSaving] = useState(false)

  // Live line total preview while editing
  const liveLineTotal = editing
    ? (Number(qty) || 0) * (Number(price) || 0)
    : (item.line_total ?? 0)

  const handleQtyChange = (v: string) => {
    setQty(v)
    onLocalChange(item.id, { qty: Number(v) || 0, unit_price: Number(price) || 0 })
  }

  const handlePriceChange = (v: string) => {
    setPrice(v)
    onLocalChange(item.id, { qty: Number(qty) || 0, unit_price: Number(v) || 0 })
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateLineItem(orderId, item.id, {
        qty: qty ? Number(qty) : undefined,
        unit_price: price ? Number(price) : undefined,
      })
      setEditing(false)
      onSaved()
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setQty(String(item.qty ?? ''))
    setPrice(String(item.unit_price ?? ''))
    setEditing(false)
    onLocalChange(item.id, { qty: item.qty ?? 0, unit_price: item.unit_price ?? 0 })
  }

  return (
    <tr style={!item.is_valid ? { background: 'rgba(239,68,68,0.04)' } : {}}>
      <td className="mono-data" style={{ color: item.is_valid ? 'var(--text-secondary)' : '#ef4444', fontSize: 11 }}>
        {item.material_code || <span style={{ color: '#ef4444' }}>UNKNOWN</span>}
      </td>
      <td style={{ fontSize: 11, maxWidth: 160 }}>
        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {item.description || '—'}
        </div>
        {item.rejection_reason && (
          <div style={{ fontSize: 10, color: '#ef4444', marginTop: 2, whiteSpace: 'normal' }}>
            <AlertTriangle size={9} style={{ display: 'inline', marginRight: 3 }} />
            {item.rejection_reason}
          </div>
        )}
      </td>
      <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.uom || '—'}</td>
      <td>
        {editing ? (
          <input className="input input-sm" style={{ width: 65 }} value={qty} onChange={e => handleQtyChange(e.target.value)} />
        ) : (
          <span className="mono-data">{item.qty ?? '—'}</span>
        )}
      </td>
      <td>
        {editing ? (
          <input className="input input-sm" style={{ width: 80 }} value={price} onChange={e => handlePriceChange(e.target.value)} />
        ) : (
          <span className="mono-data">{item.unit_price != null ? `₹${item.unit_price}` : '—'}</span>
        )}
      </td>
      <td className="mono-data" style={{ fontSize: 11 }}>{item.tax_rate != null ? `${item.tax_rate}%` : '—'}</td>
      <td className="mono-data" style={{ color: editing ? '#f59e0b' : 'inherit' }}>
        {formatCurrency(liveLineTotal)}
      </td>
      <td>
        {item.is_valid
          ? <span style={{ color: '#10b981', fontSize: 11 }}>✓ Valid</span>
          : <span style={{ color: '#ef4444', fontSize: 11 }}>✕ Invalid</span>
        }
      </td>
      {canEdit && (
        <td>
          {editing ? (
            <div style={{ display: 'flex', gap: 4 }}>
              <button className="btn btn-success btn-sm btn-icon" onClick={handleSave} disabled={saving}>
                <Save size={11} />
              </button>
              <button className="btn btn-ghost btn-sm btn-icon" onClick={handleCancel}>
                <X size={11} />
              </button>
            </div>
          ) : (
            <button className="btn btn-ghost btn-sm btn-icon" onClick={() => setEditing(true)}>
              <Edit2 size={11} />
            </button>
          )}
        </td>
      )}
    </tr>
  )
}

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: '1px solid var(--border)', gap: 8 }}>
      <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: 12, color: 'var(--text-secondary)', textAlign: 'right' }}>{children}</span>
    </div>
  )
}