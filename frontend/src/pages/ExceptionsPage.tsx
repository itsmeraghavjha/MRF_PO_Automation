import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, RefreshCw, CheckCircle2 } from 'lucide-react'
import { getOrders, type OrderSummary } from '../services/api'
import { StatusBadge, formatCurrency, formatRelativeTime, CustomerChip } from '../components/shared/StatusBadge'

export default function ExceptionsPage() {
  const navigate = useNavigate()
  const [orders, setOrders] = useState<OrderSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)

  const load = async () => {
    setLoading(true)
    try {
      const result = await getOrders({ status: 'VALIDATION_FAILED', page_size: 50 })
      setOrders(result.orders)
      setTotal(result.total)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  return (
    <div style={{ padding: '20px' }} className="animate-fade">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em' }}>Exception Queue</h2>
            {total > 0 && (
              <span style={{
                background: 'var(--status-failed-bg)', color: 'var(--status-failed)',
                fontSize: 11, fontWeight: 700, padding: '1px 7px', borderRadius: 10,
                border: '1px solid rgba(200,39,45,0.15)'
              }}>
                {total}
              </span>
            )}
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 1 }}>
            Orders that failed validation — click to review and resolve
          </p>
        </div>
        <button className="btn btn-ghost btn-icon" onClick={load}><RefreshCw size={12} /></button>
      </div>

      {/* Info banner */}
      <div style={{
        background: 'rgba(180,83,9,0.06)', border: '1px solid rgba(180,83,9,0.15)',
        borderRadius: 8, padding: '8px 12px', marginBottom: 12,
        display: 'flex', alignItems: 'center', gap: 8, fontSize: 12
      }}>
        <AlertTriangle size={12} style={{ color: 'var(--accent-amber)', flexShrink: 0 }} />
        <span style={{ color: 'var(--text-secondary)' }}>
          Click any order to open the split-view portal, edit line items, re-validate, and push to SAP.
        </span>
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
          <div className="spinner" style={{ width: 22, height: 22 }} />
        </div>
      ) : orders.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <CheckCircle2 size={36} style={{ color: '#10b981', opacity: 0.5 }} />
            <div style={{ fontSize: 14, fontWeight: 700, color: '#10b981' }}>All clear</div>
            <div style={{ fontSize: 12 }}>No exceptions pending review</div>
          </div>
        </div>
      ) : (
        /* Table view — more info-dense than cards */
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>PO Number</th>
                <th>Customer</th>
                <th>Received</th>
                <th>Value</th>
                <th>Failed Lines</th>
                <th>Failure Reason</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {orders.map(order => (
                <tr
                  key={order.id}
                  onClick={() => navigate(`/orders/${order.id}`)}
                  style={{ borderLeft: '3px solid rgba(200,39,45,0.3)' }}
                >
                  <td className="mono-data primary" style={{ fontSize: 11 }}>{order.po_number}</td>
                  <td><CustomerChip code={order.customer_code} name={order.customer_name} /></td>
                  <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>{formatRelativeTime(order.created_at)}</td>
                  <td className="mono-data">{formatCurrency(order.total_value)}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#C8272D', fontWeight: 600 }}>
                    {order.failed_line_count} / {order.line_item_count}
                  </td>
                  <td style={{ maxWidth: 260 }}>
                    {order.rejection_summary ? (
                      <span style={{
                        fontSize: 11, color: '#C8272D',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block'
                      }} title={order.rejection_summary}>
                        {order.rejection_summary}
                      </span>
                    ) : '—'}
                  </td>
                  <td><StatusBadge status={order.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}