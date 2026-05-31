import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, RefreshCw, CheckCircle2 } from 'lucide-react'
import { getOrders, type OrderSummary } from '../services/api'
import { StatusBadge, formatCurrency, formatDateTime, CustomerChip } from '../components/shared/StatusBadge'

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
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return (
    <div style={{ padding: '28px' }} className="animate-fade">
      {/* Header */}
      <div style={{ marginBottom: 24, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h2 style={{ fontSize: 24, fontWeight: 800, fontFamily: 'var(--font-display)', margin: 0 }}>
              Exception Queue
            </h2>
            {total > 0 && (
              <span style={{
                background: 'var(--status-failed-bg)', color: 'var(--status-failed)',
                fontSize: 12, fontWeight: 700, padding: '2px 10px', borderRadius: 12
              }}>
                {total} pending
              </span>
            )}
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, margin: '4px 0 0' }}>
            Orders that failed validation and require manual review
          </p>
        </div>
        <button className="btn btn-ghost btn-sm btn-icon" onClick={load}>
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Info banner */}
      <div style={{
        background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)',
        borderRadius: 10, padding: '12px 16px', marginBottom: 20,
        display: 'flex', alignItems: 'center', gap: 10, fontSize: 13
      }}>
        <AlertTriangle size={14} style={{ color: '#f59e0b', flexShrink: 0 }} />
        <span style={{ color: 'var(--text-secondary)' }}>
          Click any order to view line-item details, edit values, and re-validate.
          Once validated, you can push directly to SAP.
        </span>
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
          <div className="spinner" style={{ width: 28, height: 28 }} />
        </div>
      ) : orders.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <CheckCircle2 size={48} style={{ color: '#10b981', opacity: 0.6 }} />
            <div style={{ fontSize: 16, fontWeight: 700, color: '#10b981' }}>All clear!</div>
            <div style={{ fontSize: 13 }}>No exceptions pending review</div>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {orders.map(order => (
            <ExceptionCard key={order.id} order={order} onClick={() => navigate(`/orders/${order.id}`)} />
          ))}
        </div>
      )}
    </div>
  )
}

function ExceptionCard({ order, onClick }: { order: OrderSummary; onClick: () => void }) {
  return (
    <div
      className="card"
      onClick={onClick}
      style={{
        cursor: 'pointer', transition: 'all 0.15s',
        borderColor: 'rgba(239,68,68,0.2)',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(239,68,68,0.5)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(239,68,68,0.2)')}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              {order.po_number}
            </span>
            <StatusBadge status={order.status} />
          </div>
          <CustomerChip code={order.customer_code} name={order.customer_name} />
          {order.rejection_summary && (
            <div style={{
              marginTop: 8, padding: '6px 10px',
              background: 'rgba(239,68,68,0.06)', borderRadius: 6,
              fontSize: 12, color: '#ef4444'
            }}>
              <AlertTriangle size={10} style={{ display: 'inline', marginRight: 5 }} />
              {order.rejection_summary}
            </div>
          )}
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
            {formatCurrency(order.total_value)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            {formatDateTime(order.created_at)}
          </div>
          <div style={{ fontSize: 11, color: '#ef4444', marginTop: 4 }}>
            {order.failed_line_count} line{order.failed_line_count !== 1 ? 's' : ''} failed
          </div>
        </div>
      </div>
    </div>
  )
}