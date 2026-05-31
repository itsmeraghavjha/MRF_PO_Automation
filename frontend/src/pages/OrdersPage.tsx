import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Filter, RefreshCw, Package } from 'lucide-react'
import { getOrders, type OrderSummary, type OrderListResponse } from '../services/api'
import { StatusBadge, formatCurrency, formatDateTime, CustomerChip } from '../components/shared/StatusBadge'

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
      const result = await getOrders({ page, page_size: 20, status: status || undefined, search: search || undefined })
      setData(result)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [page, status, search])

  useEffect(() => { load() }, [load])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearch(searchInput)
    setPage(1)
  }

  const handleStatusChange = (val: string) => {
    setStatus(val)
    setPage(1)
  }

  const totalPages = data ? Math.ceil(data.total / 20) : 0

  return (
    <div style={{ padding: '28px' }} className="animate-fade">
      {/* Header */}
      <div style={{ marginBottom: 24, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: 24, fontWeight: 800, fontFamily: 'var(--font-display)', marginBottom: 4 }}>
            All Orders
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, margin: 0 }}>
            {data ? `${data.total} purchase orders` : 'Loading…'}
          </p>
        </div>
        <button className="btn btn-ghost btn-sm btn-icon" onClick={load}>
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8, flex: 1 }}>
          <div style={{ position: 'relative', flex: 1, maxWidth: 340 }}>
            <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
            <input
              className="input input-sm"
              style={{ paddingLeft: 30 }}
              placeholder="Search PO number, customer…"
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-secondary btn-sm">
            Search
          </button>
          {search && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setSearch(''); setSearchInput(''); setPage(1) }}>
              Clear
            </button>
          )}
        </form>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Filter size={13} style={{ color: 'var(--text-muted)' }} />
          <select
            className="input input-sm"
            style={{ width: 'auto', minWidth: 160 }}
            value={status}
            onChange={e => handleStatusChange(e.target.value)}
          >
            {STATUS_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
            <div className="spinner" style={{ width: 28, height: 28 }} />
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
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data?.orders.map(order => (
                  <OrderRow key={order.id} order={order} onClick={() => navigate(`/orders/${order.id}`)} />
                ))}
              </tbody>
            </table>

            {(!data?.orders.length) && (
              <div className="empty-state">
                <Package size={40} className="empty-state-icon" />
                <div style={{ fontSize: 14, fontWeight: 600 }}>No orders found</div>
                <div style={{ fontSize: 12 }}>Try adjusting your filters</div>
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '12px 16px', borderTop: '1px solid var(--border)'
              }}>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  Page {page} of {totalPages} · {data?.total} total
                </span>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button className="btn btn-secondary btn-sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
                    ← Prev
                  </button>
                  <button className="btn btn-secondary btn-sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
                    Next →
                  </button>
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
      <td className="primary mono-data">{order.po_number}</td>
      <td><CustomerChip code={order.customer_code} name={order.customer_name} /></td>
      <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{formatDateTime(order.created_at)}</td>
      <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{order.po_date || '—'}</td>
      <td className="mono-data">{formatCurrency(order.total_value)}</td>
      <td style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
        {order.line_item_count}
        {order.failed_line_count > 0 && (
          <span style={{ color: '#ef4444', marginLeft: 4 }}>({order.failed_line_count} ✕)</span>
        )}
      </td>
      <td><StatusBadge status={order.status} /></td>
    </tr>
  )
}