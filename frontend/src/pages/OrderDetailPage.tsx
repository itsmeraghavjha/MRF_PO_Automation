import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, RefreshCw, Send, CheckCircle2, AlertTriangle,
  Clock, FileText, Edit2, Save, X, ExternalLink
} from 'lucide-react'
import {
  getOrder, revalidateOrder, pushToSAP, updateLineItem,
  type OrderDetail, type LineItem
} from '../services/api'
import { StatusBadge, formatCurrency, formatDate, formatRelativeTime, CustomerChip } from '../components/shared/StatusBadge'
import { DeliveryRequestButton } from '../components/shared/DeliveryRequestButton'

const EVENT_LABELS: Record<string, string> = {
  LINE_EDIT: 'Line item edited',
  REVALIDATED: 'Re-validation run',
  SAP_PUSHED: 'SAP CSV generated',
  STATUS_CHANGE: 'Status updated',
  DELIVERY_REQUEST_SENT: 'Delivery request sent',
  DELIVERY_DATE_CONFIRMED: 'Delivery date confirmed',
}

function humanEvent(type: string) {
  return EVENT_LABELS[type] || type.replace(/_/g, ' ').toLowerCase()
}

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
    } catch (e: any) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [id])

  const handleRevalidate = async () => {
    if (!order) return
    setActionLoading(true); setError(null)
    try {
      await revalidateOrder(order.id)
      await load()
      setSuccessMsg('Re-validation complete')
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (e: any) { setError(e.message) }
    finally { setActionLoading(false) }
  }

  const handleSAPPush = async () => {
    if (!order) return
    setActionLoading(true); setError(null)
    try {
      const result = await pushToSAP(order.id)
      await load()
      setSuccessMsg(`SAP CSV: ${result.csv_filename}`)
      setTimeout(() => setSuccessMsg(null), 5000)
    } catch (e: any) { setError(e.message) }
    finally { setActionLoading(false) }
  }

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
      <div className="spinner" style={{ width: 24, height: 24 }} />
    </div>
  )

  if (!order) return <div style={{ padding: 20, color: 'var(--status-failed)' }}>Order not found.</div>

  const canPushSAP = order.status === 'VALIDATED'
  const canRevalidate = ['VALIDATION_FAILED', 'VALIDATED', 'AWAITING_DELIVERY_DATE'].includes(order.status)
  const hasPdf = !!pdfUrl && pdfUrl.toLowerCase().endsWith('.pdf')

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* ── LEFT PANEL ── */}
      <div style={{
        flex: showPdf && hasPdf ? '0 0 56%' : '1 1 100%',
        overflowY: 'auto',
        padding: '16px 18px',
        transition: 'flex 0.25s ease',
        borderRight: showPdf && hasPdf ? '1px solid var(--border)' : 'none',
      }}>
        {/* Header row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <button className="btn btn-ghost btn-icon" onClick={() => navigate('/orders')}>
            <ArrowLeft size={14} />
          </button>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '-0.01em' }}>
                {order.po_number}
              </span>
              <StatusBadge status={order.status} />
              {order.is_update && (
                <span className="badge" style={{ background: 'rgba(194,119,10,0.1)', color: 'var(--accent-amber)' }}>REVISED</span>
              )}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
              {formatRelativeTime(order.created_at)} · {order.email_sender}
            </div>
          </div>
          {/* Action buttons */}
          <div style={{ display: 'flex', gap: 5, flexShrink: 0 }}>
            {hasPdf && (
              <button className="btn btn-ghost btn-sm" onClick={() => setShowPdf(s => !s)}>
                <FileText size={11} /> {showPdf ? 'Hide PDF' : 'PDF'}
              </button>
            )}
            <button className="btn btn-ghost btn-icon" onClick={load} disabled={actionLoading}>
              <RefreshCw size={12} />
            </button>
            {canRevalidate && (
              <button className="btn btn-secondary btn-sm" onClick={handleRevalidate} disabled={actionLoading}>
                <RefreshCw size={11} /> Revalidate
              </button>
            )}
            {canPushSAP && (
              <button className="btn btn-primary btn-sm" onClick={handleSAPPush} disabled={actionLoading}>
                <Send size={11} /> Push to SAP
              </button>
            )}
          </div>
        </div>

        {/* Delivery request */}
        <div style={{ marginBottom: 10 }}>
          <DeliveryRequestButton
            orderId={order.id}
            orderStatus={order.status}
            deliveryDate={order.delivery_date}
            onSuccess={load}
          />
        </div>

        {/* Alerts */}
        {error && (
          <div className="alert alert-error" style={{ marginBottom: 10 }}>
            <AlertTriangle size={12} style={{ flexShrink: 0 }} /> {error}
          </div>
        )}
        {successMsg && (
          <div className="alert alert-success" style={{ marginBottom: 10 }}>
            <CheckCircle2 size={12} style={{ flexShrink: 0 }} /> {successMsg}
          </div>
        )}
        {order.status === 'AWAITING_DELIVERY_DATE' && (
          <div className="alert alert-warning" style={{ marginBottom: 10 }}>
            <Clock size={12} style={{ flexShrink: 0 }} />
            <span>Awaiting vendor delivery date confirmation.</span>
          </div>
        )}
        {order.rejection_summary && (
          <div className="alert alert-error" style={{ marginBottom: 10 }}>
            <AlertTriangle size={12} style={{ flexShrink: 0 }} />
            <span><strong>Failures:</strong> {order.rejection_summary}</span>
          </div>
        )}

        {/* ── Compact Meta Grid ── */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr',
          gap: 8, marginBottom: 12
        }}>
          {/* Order Info */}
          <div className="card" style={{ padding: '10px 12px' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>Order</div>
            <MetaGrid rows={[
              ['Customer', <CustomerChip code={order.customer_code} name={order.customer_name} />],
              ['PO Date', order.po_date || '—'],
              ['Delivery', order.delivery_date
                ? <span style={{ color: '#1E6B3C', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{formatDate(order.delivery_date)}</span>
                : <span style={{ color: 'var(--accent-amber)', display: 'flex', alignItems: 'center', gap: 3 }}><Clock size={10} />Not set</span>
              ],
              ['Total Value', <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600 }}>{formatCurrency(order.total_value)}</span>],
              ['Lines', `${order.line_item_count} (${order.failed_line_count} failed)`],
            ]} />
          </div>

          {/* Ship-to & Legal */}
          <div className="card" style={{ padding: '10px 12px' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>Dispatch & Legal</div>
            <MetaGrid rows={[
              ['Ship-to Code', order.ship_to_code
                ? <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{order.ship_to_code}</span>
                : <span style={{ color: '#C8272D', fontSize: 11 }}>Not mapped</span>
              ],
              ['Address', <span style={{ fontSize: 11, color: 'var(--text-muted)' }} title={order.ship_to_address || ''}>{order.ship_to_address?.slice(0, 40) || '—'}</span>],
              ['Sales District', order.sales_district || <span style={{ color: 'var(--text-subtle)' }}>—</span>],
              ['GSTIN', order.vendor_gstin
                ? <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>{order.vendor_gstin}</span>
                : <span style={{ color: '#C8272D', fontSize: 11 }}>Missing</span>
              ],
              ['Attachment', pdfUrl
                ? <a href={pdfUrl} target="_blank" rel="noreferrer"
                    style={{ color: 'var(--accent-blue)', fontSize: 11, display: 'flex', alignItems: 'center', gap: 3 }}>
                    <ExternalLink size={10} /> Open file
                  </a>
                : <span style={{ color: 'var(--text-subtle)', fontSize: 11 }}>—</span>
              ],
            ]} />
          </div>
        </div>

        {/* Line Items */}
        <LineItemsTable order={order} onSaved={load} canEdit={order.status !== 'SAP_SUCCESS'} />

        {/* Audit Log */}
        <div className="card" style={{ marginTop: 10, padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontSize: 12, fontWeight: 600 }}>Audit Trail</span>
          </div>
          <div style={{ maxHeight: 180, overflowY: 'auto' }}>
            {order.audit_logs.length === 0 && (
              <div style={{ padding: '16px', color: 'var(--text-muted)', fontSize: 11, textAlign: 'center' }}>
                No events yet
              </div>
            )}
            {order.audit_logs.map(log => (
              <div key={log.id} style={{
                display: 'flex', gap: 8, padding: '6px 12px',
                borderBottom: '1px solid var(--neutral-100)', alignItems: 'flex-start'
              }}>
                <div style={{
                  width: 5, height: 5, borderRadius: '50%', marginTop: 5, flexShrink: 0,
                  background: log.event_type === 'SAP_PUSHED' ? '#3b82f6'
                    : log.event_type.includes('DELIVERY') ? '#f59e0b'
                    : 'var(--brand-green)'
                }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    {log.description}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>
                    {humanEvent(log.event_type)} · {log.performed_by} · {formatRelativeTime(log.created_at)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── RIGHT PANEL: PDF ── */}
      {showPdf && hasPdf && (
        <div style={{
          flex: '0 0 44%',
          display: 'flex', flexDirection: 'column',
          background: '#1a2332',
          borderLeft: '1px solid var(--border)'
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '7px 12px', borderBottom: '1px solid var(--border)',
            background: 'var(--bg-surface)', flexShrink: 0
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <FileText size={12} color="var(--accent-amber)" />
              <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>Original PO</span>
            </div>
            <div style={{ display: 'flex', gap: 5 }}>
              <a href={pdfUrl!} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm">
                <ExternalLink size={10} /> Open
              </a>
              <button className="btn btn-ghost btn-icon" onClick={() => setShowPdf(false)}>
                <X size={12} />
              </button>
            </div>
          </div>
          <iframe src={pdfUrl!} style={{ flex: 1, border: 'none', width: '100%' }} title="PO Document" />
        </div>
      )}
    </div>
  )
}

// ── Compact Meta Grid ──────────────────────────────────────────────────────
function MetaGrid({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      {rows.map(([label, value], i) => (
        <div key={i} style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '4px 0',
          borderBottom: i < rows.length - 1 ? '1px solid var(--neutral-100)' : 'none',
          gap: 8
        }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 500, flexShrink: 0 }}>{label}</span>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', textAlign: 'right' }}>{value}</span>
        </div>
      ))}
    </div>
  )
}

// ── Line Items Table ──────────────────────────────────────────────────────
function LineItemsTable({ order, onSaved, canEdit }: {
  order: OrderDetail; onSaved: () => void; canEdit: boolean
}) {
  const [lineItems, setLineItems] = useState(order.line_items)
  useEffect(() => { setLineItems(order.line_items) }, [order.line_items])

  const updateLocalItem = (id: number, changes: Partial<LineItem>) => {
    setLineItems(prev => prev.map(item => item.id === id ? { ...item, ...changes } : item))
  }

  const liveTotal = lineItems.reduce((sum, item) => sum + (item.qty ?? 0) * (item.unit_price ?? 0), 0)
  const originalTotal = order.total_value ?? 0
  const totalChanged = Math.abs(liveTotal - originalTotal) > 0.01

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{
        padding: '8px 12px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between'
      }}>
        <span style={{ fontSize: 12, fontWeight: 600 }}>
          Line Items <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>({lineItems.length})</span>
        </span>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700,
          color: totalChanged ? 'var(--accent-amber)' : '#1E6B3C'
        }}>
          {formatCurrency(totalChanged ? liveTotal : originalTotal)}
        </span>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Material</th>
              <th>Description</th>
              <th>UOM</th>
              <th>Qty</th>
              <th>Unit Price</th>
              <th>Line Total</th>
              <th>Valid</th>
              {canEdit && <th style={{ width: 60 }}></th>}
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

function LineItemRow({ item, orderId, onSaved, onLocalChange, canEdit }: {
  item: LineItem; orderId: number; onSaved: () => void
  onLocalChange: (id: number, changes: Partial<LineItem>) => void; canEdit: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [qty, setQty] = useState(String(item.qty ?? ''))
  const [price, setPrice] = useState(String(item.unit_price ?? ''))
  const [saving, setSaving] = useState(false)

  const liveTotal = editing
    ? (Number(qty) || 0) * (Number(price) || 0)
    : (item.line_total ?? 0)

  const handleQtyChange = (v: string) => { setQty(v); onLocalChange(item.id, { qty: Number(v) || 0, unit_price: Number(price) || 0 }) }
  const handlePriceChange = (v: string) => { setPrice(v); onLocalChange(item.id, { qty: Number(qty) || 0, unit_price: Number(v) || 0 }) }

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateLineItem(orderId, item.id, {
        qty: qty ? Number(qty) : undefined,
        unit_price: price ? Number(price) : undefined,
      })
      setEditing(false)
      onSaved()
    } catch (e) { console.error(e) }
    finally { setSaving(false) }
  }

  const handleCancel = () => {
    setQty(String(item.qty ?? '')); setPrice(String(item.unit_price ?? ''))
    setEditing(false)
    onLocalChange(item.id, { qty: item.qty ?? 0, unit_price: item.unit_price ?? 0 })
  }

  return (
    <tr style={!item.is_valid ? { background: 'rgba(200,39,45,0.03)' } : {}}>
      <td className="mono-data" style={{
        color: item.is_valid ? 'var(--text-secondary)' : '#C8272D', fontSize: 11
      }}>
        {item.material_code || <span style={{ color: '#C8272D' }}>UNKNOWN</span>}
      </td>
      <td style={{ fontSize: 11, maxWidth: 160 }}>
        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.description || '—'}</div>
        {item.rejection_reason && (
          <div style={{ fontSize: 10, color: '#C8272D', marginTop: 1, display: 'flex', alignItems: 'flex-start', gap: 3 }}>
            <AlertTriangle size={9} style={{ flexShrink: 0, marginTop: 1 }} />
            <span style={{ whiteSpace: 'normal', lineHeight: 1.3 }}>{item.rejection_reason}</span>
          </div>
        )}
      </td>
      <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.uom || '—'}</td>
      <td>
        {editing
          ? <input className="input input-sm" style={{ width: 60 }} value={qty} onChange={e => handleQtyChange(e.target.value)} />
          : <span className="mono-data">{item.qty ?? '—'}</span>
        }
      </td>
      <td>
        {editing
          ? <input className="input input-sm" style={{ width: 75 }} value={price} onChange={e => handlePriceChange(e.target.value)} />
          : <span className="mono-data">{item.unit_price != null ? `₹${item.unit_price}` : '—'}</span>
        }
      </td>
      <td className="mono-data" style={{ color: editing ? 'var(--accent-amber)' : 'inherit' }}>
        {formatCurrency(liveTotal)}
      </td>
      <td>
        {item.is_valid
          ? <span style={{ color: '#1E6B3C', fontSize: 11, fontWeight: 600 }}>✓</span>
          : <span style={{ color: '#C8272D', fontSize: 11, fontWeight: 600 }}>✕</span>
        }
      </td>
      {canEdit && (
        <td>
          {editing ? (
            <div style={{ display: 'flex', gap: 3 }}>
              <button className="btn btn-success btn-sm btn-icon" onClick={handleSave} disabled={saving}><Save size={10} /></button>
              <button className="btn btn-ghost btn-sm btn-icon" onClick={handleCancel}><X size={10} /></button>
            </div>
          ) : (
            <button className="btn btn-ghost btn-sm btn-icon" onClick={() => setEditing(true)}><Edit2 size={10} /></button>
          )}
        </td>
      )}
    </tr>
  )
}