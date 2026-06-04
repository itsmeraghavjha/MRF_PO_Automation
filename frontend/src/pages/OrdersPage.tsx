import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Filter, RefreshCw, Package } from 'lucide-react'
import { getOrders, type OrderSummary, type OrderListResponse } from '../services/api'
import { StatusBadge, formatCurrency, formatRelativeTime, CustomerChip } from '../components/shared/StatusBadge'

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'NEW', label: 'Processing' },
  { value: 'VALIDATED', label: 'Ready for SAP' },
  { value: 'VALIDATION_FAILED', label: 'Needs Review' },
  { value: 'AWAITING_DELIVERY_DATE', label: 'Awaiting Date' },
  { value: 'SAP_SUCCESS', label: 'SAP Pushed' },
]

export default function OrdersPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<OrderListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await getOrders({ page, page_size: 25, status: status || undefined, search: search || undefined })
      setData(result)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [page, status, search])

  useEffect(() => { load() }, [load])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearch(searchInput)
    setPage(1)
  }

  const handleStatusChange = (val: string) => { setStatus(val); setPage(1) }
  const totalPages = data ? Math.ceil(data.total / 25) : 0

  return (
    <div style={{ padding: '20px' }} className="animate-fade">
      {/* Header + Toolbar — single row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 1 }}>Orders</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: 11 }}>
            {data ? `${data.total} purchase orders` : 'Loading…'}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Search */}
          <form onSubmit={handleSearch} style={{ display: 'flex', gap: 6 }}>
            <div style={{ position: 'relative' }}>
              <Search size={11} style={{
                position: 'absolute', left: 8, top: '50%',
                transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none'
              }} />
              <input
                className="input input-sm"
                style={{ paddingLeft: 26, width: 200 }}
                placeholder="PO number, customer…"
                value={searchInput}
                onChange={e => setSearchInput(e.target.value)}
              />
            </div>
            <button type="submit" className="btn btn-secondary btn-sm">Search</button>
            {search && (
              <button type="button" className="btn btn-ghost btn-sm"
                onClick={() => { setSearch(''); setSearchInput(''); setPage(1) }}>
                Clear
              </button>
            )}
          </form>
          {/* Status filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <Filter size={11} style={{ color: 'var(--text-muted)' }} />
            <select
              className="input input-sm"
              style={{ width: 'auto', minWidth: 140 }}
              value={status}
              onChange={e => handleStatusChange(e.target.value)}
            >
              {STATUS_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <button className="btn btn-ghost btn-icon" onClick={load}><RefreshCw size={12} /></button>
        </div>
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
            <div className="spinner" style={{ width: 22, height: 22 }} />
          </div>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>PO Number</th>
                  <th>Customer</th>
                  <th>Received</th>
                  <th>PO Date</th>
                  <th>Value</th>
                  <th>Lines</th>
                  <th>Rejection</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data?.orders.map(order => (
                  <OrderRow key={order.id} order={order} onClick={() => navigate(`/orders/${order.id}`)} />
                ))}
              </tbody>
            </table>

            {!data?.orders.length && (
              <div className="empty-state">
                <Package size={32} className="empty-state-icon" />
                <div style={{ fontSize: 13, fontWeight: 600 }}>No orders found</div>
                <div style={{ fontSize: 11 }}>Try adjusting your filters</div>
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 14px', borderTop: '1px solid var(--border)'
              }}>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  Page {page} of {totalPages} · {data?.total} total
                </span>
                <div style={{ display: 'flex', gap: 5 }}>
                  <button className="btn btn-secondary btn-sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
                  <button className="btn btn-secondary btn-sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next →</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function OrderRow({ order, onClick }: { order: OrderSummary; onClick: () => void }) {
  return (
    <tr onClick={onClick}>
      <td className="primary mono-data" style={{ fontSize: 11 }}>{order.po_number}</td>
      <td><CustomerChip code={order.customer_code} name={order.customer_name} /></td>
      <td style={{ color: 'var(--text-muted)', fontSize: 11 }}>{formatRelativeTime(order.created_at)}</td>
      <td style={{ color: 'var(--text-muted)', fontSize: 11 }}>{order.po_date || '—'}</td>
      <td className="mono-data">{formatCurrency(order.total_value)}</td>
      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
        {order.line_item_count}
        {order.failed_line_count > 0 && (
          <span style={{ color: '#C8272D', marginLeft: 3 }}>({order.failed_line_count}✕)</span>
        )}
      </td>
      <td style={{ maxWidth: 180 }}>
        {order.rejection_summary ? (
          <span style={{
            fontSize: 10, color: '#C8272D',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block'
          }} title={order.rejection_summary}>
            {order.rejection_summary}
          </span>
        ) : <span style={{ color: 'var(--text-subtle)', fontSize: 11 }}>—</span>}
      </td>
      <td><StatusBadge status={order.status} /></td>
    </tr>
  )
}