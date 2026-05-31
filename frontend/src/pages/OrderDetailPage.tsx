import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, RefreshCw, Send, CheckCircle2, AlertTriangle,
  Clock, FileText, Edit2, Save, X
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

  const load = async () => {
    if (!id) return
    setLoading(true)
    try {
      const o = await getOrder(Number(id))
      setOrder(o)
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
    return (
      <div style={{ padding: 28 }}>
        <div style={{ color: 'var(--status-failed)' }}>Order not found.</div>
      </div>
    )
  }

  const canPushSAP = order.status === 'VALIDATED'
  const canRevalidate = ['VALIDATION_FAILED', 'VALIDATED', 'AWAITING_DELIVERY_DATE'].includes(order.status)

  return (
    <div style={{ padding: '28px' }} className="animate-fade">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <button className="btn btn-ghost btn-sm btn-icon" onClick={() => navigate('/orders')}>
          <ArrowLeft size={15} />
        </button>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h2 style={{ fontSize: 22, fontWeight: 800, fontFamily: 'var(--font-display)', margin: 0 }}>
              {order.po_number}
            </h2>
            <StatusBadge status={order.status} />
            {order.is_update && (
              <span className="badge" style={{ background: 'rgba(226,168,75,0.12)', color: '#e2a84b' }}>
                REVISED
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
            Received {formatDateTime(order.created_at)} · {order.email_sender}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm btn-icon" onClick={load} disabled={actionLoading}>
            <RefreshCw size={13} />
          </button>
          {canRevalidate && (
            <button className="btn btn-secondary btn-sm" onClick={handleRevalidate} disabled={actionLoading}>
              <RefreshCw size={13} />
              Re-validate
            </button>
          )}
          {canPushSAP && (
            <button className="btn btn-primary btn-sm" onClick={handleSAPPush} disabled={actionLoading}>
              <Send size={13} />
              Push to SAP
            </button>
          )}
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#ef4444', fontSize: 13 }}>
          {error}
        </div>
      )}
      {successMsg && (
        <div style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#10b981', fontSize: 13 }}>
          <CheckCircle2 size={13} style={{ display: 'inline', marginRight: 6 }} />
          {successMsg}
        </div>
      )}
      {order.rejection_summary && (
        <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: '10px 14px', marginBottom: 16, fontSize: 13 }}>
          <AlertTriangle size={13} style={{ display: 'inline', marginRight: 6, color: '#ef4444' }} />
          <span style={{ color: '#ef4444', fontWeight: 600 }}>Validation failures: </span>
          <span style={{ color: 'var(--text-secondary)' }}>{order.rejection_summary}</span>
        </div>
      )}

      {/* Two-column meta */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 20 }}>
        <div className="card">
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
            Order Info
          </div>
          <MetaRow label="Customer"><CustomerChip code={order.customer_code} name={order.customer_name} /></MetaRow>
          <MetaRow label="PO Date">{order.po_date || '—'}</MetaRow>
          <MetaRow label="Delivery Date">
            {order.delivery_date
              ? <span style={{ color: '#10b981' }}>{formatDate(order.delivery_date)}</span>
              : <span style={{ color: '#f59e0b', display: 'flex', alignItems: 'center', gap: 4 }}><Clock size={11} /> Not set</span>
            }
          </MetaRow>
          <MetaRow label="Total Value">{formatCurrency(order.total_value)}</MetaRow>
          <MetaRow label="Lines">{order.line_item_count} ({order.failed_line_count} failed)</MetaRow>
        </div>

        <div className="card">
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
            Delivery & Legal
          </div>
          <MetaRow label="Ship To Code">{order.ship_to_code || <span style={{ color: '#ef4444' }}>Not mapped</span>}</MetaRow>
          <MetaRow label="Ship To Address">{order.ship_to_address || '—'}</MetaRow>
          <MetaRow label="Vendor GSTIN">
            {order.vendor_gstin
              ? <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{order.vendor_gstin}</span>
              : <span style={{ color: '#ef4444' }}>Missing</span>
            }
          </MetaRow>
          {order.drive_link && (
            <MetaRow label="Attachment">
              <a href={`/pdfs/${order.drive_link.split('/').pop()}`} target="_blank" rel="noreferrer"
                style={{ color: 'var(--accent-blue)', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <FileText size={11} /> View file
              </a>
            </MetaRow>
          )}
        </div>
      </div>

      {/* Line Items */}
      <div className="card" style={{ marginBottom: 20, padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-display)', margin: 0 }}>
            Line Items
          </h3>
        </div>
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
              <th></th>
            </tr>
          </thead>
          <tbody>
            {order.line_items.map(item => (
              <LineItemRow
                key={item.id}
                item={item}
                orderId={order.id}
                onSaved={handleLineItemSaved}
                canEdit={order.status !== 'SAP_SUCCESS'}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Audit Log */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-display)', margin: 0 }}>
            Audit Trail
          </h3>
        </div>
        <div style={{ padding: '8px 0' }}>
          {order.audit_logs.length === 0 && (
            <div style={{ padding: '20px', color: 'var(--text-muted)', fontSize: 13, textAlign: 'center' }}>
              No audit events yet
            </div>
          )}
          {order.audit_logs.map(log => (
            <div key={log.id} style={{
              display: 'flex', gap: 12, padding: '10px 20px',
              borderBottom: '1px solid var(--border)', alignItems: 'flex-start'
            }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-blue)',
                marginTop: 5, flexShrink: 0
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{log.description}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  {log.event_type} · {log.performed_by} · {formatDateTime(log.created_at)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--border)', gap: 8 }}>
      <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: 13, color: 'var(--text-secondary)', textAlign: 'right' }}>{children}</span>
    </div>
  )
}

function LineItemRow({ item, orderId, onSaved, canEdit }: {
  item: LineItem; orderId: number; onSaved: () => void; canEdit: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [qty, setQty] = useState(String(item.qty ?? ''))
  const [price, setPrice] = useState(String(item.unit_price ?? ''))
  const [saving, setSaving] = useState(false)

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

  const rowStyle = !item.is_valid
    ? { background: 'rgba(239,68,68,0.04)' }
    : {}

  return (
    <tr style={rowStyle}>
      <td className="mono-data" style={{ color: item.is_valid ? 'var(--text-secondary)' : '#ef4444', fontSize: 11 }}>
        {item.material_code || <span style={{ color: '#ef4444' }}>UNKNOWN</span>}
      </td>
      <td style={{ fontSize: 12, maxWidth: 200 }}>
        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {item.description || '—'}
        </div>
        {item.rejection_reason && (
          <div style={{ fontSize: 10, color: '#ef4444', marginTop: 2 }}>{item.rejection_reason}</div>
        )}
      </td>
      <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{item.uom || '—'}</td>
      <td>
        {editing ? (
          <input className="input input-sm" style={{ width: 70 }} value={qty} onChange={e => setQty(e.target.value)} />
        ) : (
          <span className="mono-data">{item.qty ?? '—'}</span>
        )}
      </td>
      <td>
        {editing ? (
          <input className="input input-sm" style={{ width: 90 }} value={price} onChange={e => setPrice(e.target.value)} />
        ) : (
          <span className="mono-data">{item.unit_price != null ? `₹${item.unit_price}` : '—'}</span>
        )}
      </td>
      <td className="mono-data" style={{ fontSize: 11 }}>{item.tax_rate != null ? `${item.tax_rate}%` : '—'}</td>
      <td className="mono-data">{formatCurrency(item.line_total)}</td>
      <td>
        {item.is_valid
          ? <span style={{ color: '#10b981', fontSize: 11 }}>✓ Valid</span>
          : <span style={{ color: '#ef4444', fontSize: 11 }}>✕ Invalid</span>
        }
      </td>
      <td>
        {canEdit && (
          editing ? (
            <div style={{ display: 'flex', gap: 4 }}>
              <button className="btn btn-success btn-sm btn-icon" onClick={handleSave} disabled={saving}>
                <Save size={11} />
              </button>
              <button className="btn btn-ghost btn-sm btn-icon" onClick={() => setEditing(false)}>
                <X size={11} />
              </button>
            </div>
          ) : (
            <button className="btn btn-ghost btn-sm btn-icon" onClick={() => setEditing(true)}>
              <Edit2 size={11} />
            </button>
          )
        )}
      </td>
    </tr>
  )
}