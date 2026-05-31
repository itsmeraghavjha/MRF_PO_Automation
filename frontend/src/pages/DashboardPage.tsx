import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TrendingUp, Package, AlertOctagon, CheckCircle2, Zap, ArrowUpRight, RefreshCw } from 'lucide-react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import { getDashboard, type DashboardResponse } from '../services/api'
import { StatusBadge, formatCurrency, formatDateTime, CustomerChip } from '../components/shared/StatusBadge'

export default function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())
  const navigate = useNavigate()

  const load = async () => {
    try {
      const d = await getDashboard()
      setData(d)
      setLastRefresh(new Date())
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <div className="spinner" style={{ width: 32, height: 32 }} />
      </div>
    )
  }

  const { kpis, status_breakdown, recent_orders } = data!

  const kpiCards = [
    {
      label: 'Orders Today',
      value: kpis.total_pos_today,
      sub: `${kpis.total_pos_all_time} total`,
      icon: Package,
      color: '#4f8ef7',
      trend: null,
    },
    {
      label: 'Value Today',
      value: formatCurrency(kpis.total_value_today),
      sub: `${formatCurrency(kpis.total_value_all_time)} total`,
      icon: TrendingUp,
      color: '#2dd4bf',
      trend: null,
    },
    {
      label: 'Auto-Processed',
      value: kpis.auto_processed,
      sub: `${kpis.success_rate}% success rate`,
      icon: Zap,
      color: '#10b981',
      trend: kpis.success_rate,
    },
    {
      label: 'Exceptions Pending',
      value: kpis.exceptions_pending,
      sub: 'Need manual review',
      icon: AlertOctagon,
      color: kpis.exceptions_pending > 0 ? '#ef4444' : '#10b981',
      trend: null,
      urgent: kpis.exceptions_pending > 0,
    },
  ]

  return (
    <div style={{ padding: '28px' }} className="animate-fade">
      {/* Page Header */}
      <div style={{ marginBottom: 28, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: 24, fontWeight: 800, fontFamily: 'var(--font-display)', marginBottom: 4 }}>
            Operations Dashboard
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, margin: 0 }}>
            Live PO processing status · Auto-refreshes every 10s
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Last: {lastRefresh.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
          <button className="btn btn-ghost btn-sm btn-icon" onClick={load}>
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 }}>
        {kpiCards.map(({ label, value, sub, icon: Icon, color, urgent }) => (
          <div
            key={label}
            className="card"
            style={{
              position: 'relative', overflow: 'hidden',
              borderColor: urgent ? 'rgba(239,68,68,0.3)' : 'var(--border)',
            }}
          >
            <div style={{
              position: 'absolute', top: 0, right: 0,
              width: 80, height: 80,
              background: `radial-gradient(circle at 100% 0%, ${color}20 0%, transparent 70%)`,
              pointerEvents: 'none'
            }} />
            <div style={{
              width: 36, height: 36, borderRadius: 8,
              background: `${color}18`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              marginBottom: 12
            }}>
              <Icon size={18} color={color} />
            </div>
            <div style={{
              fontSize: 28, fontWeight: 800, fontFamily: 'var(--font-display)',
              color: urgent ? '#ef4444' : 'var(--text-primary)',
              lineHeight: 1, marginBottom: 4
            }}>
              {value}
            </div>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 2 }}>
              {label}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {sub}
            </div>
          </div>
        ))}
      </div>

      {/* Middle row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: 14, marginBottom: 24 }}>
        {/* Status breakdown donut */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-display)' }}>
              Order Status Distribution
            </h3>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>All time</span>
          </div>

          <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
            <ResponsiveContainer width={160} height={160}>
              <PieChart>
                <Pie
                  data={status_breakdown}
                  cx="50%" cy="50%"
                  innerRadius={50} outerRadius={75}
                  paddingAngle={3}
                  dataKey="count"
                >
                  {status_breakdown.map((entry) => (
                    <Cell key={entry.status} fill={entry.color} stroke="transparent" />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border)',
                    borderRadius: 8, fontSize: 12
                  }}
                  formatter={(v, _, { payload }) => [v, payload.label]}
                />
              </PieChart>
            </ResponsiveContainer>

            <div style={{ flex: 1 }}>
              {status_breakdown.map((s) => (
                <div key={s.status} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '6px 0', borderBottom: '1px solid var(--border)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: 2, background: s.color, flexShrink: 0 }} />
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{s.label}</span>
                  </div>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: s.color }}>
                    {s.count}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Success rate card */}
        <div className="card" style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          textAlign: 'center', gap: 12, position: 'relative', overflow: 'hidden'
        }}>
          <div style={{
            position: 'absolute', inset: 0,
            background: `conic-gradient(
              #10b981 0deg ${kpis.success_rate * 3.6}deg,
              rgba(16,185,129,0.06) ${kpis.success_rate * 3.6}deg 360deg
            )`,
            borderRadius: 'var(--radius-lg)',
            mask: 'radial-gradient(farthest-side, transparent 58%, black 59%)',
            WebkitMask: 'radial-gradient(farthest-side, transparent 58%, black 59%)',
          }} />
          <CheckCircle2 size={20} color="#10b981" />
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 40, fontWeight: 900, color: '#10b981', lineHeight: 1 }}>
            {kpis.success_rate}%
          </div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
            Auto-Process Rate
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {kpis.sap_pushed} of {kpis.total_pos_all_time} orders
          </div>
        </div>
      </div>

      {/* Recent orders table */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-display)' }}>
            Recent Orders
          </h3>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => navigate('/orders')}
            style={{ display: 'flex', alignItems: 'center', gap: 4 }}
          >
            View all <ArrowUpRight size={12} />
          </button>
        </div>

        <table className="data-table">
          <thead>
            <tr>
              <th>PO Number</th>
              <th>Customer</th>
              <th>Date</th>
              <th>Value</th>
              <th>Lines</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {recent_orders.map((order) => (
              <tr key={order.id} onClick={() => navigate(`/orders/${order.id}`)}>
                <td className="primary mono-data">{order.po_number}</td>
                <td><CustomerChip code={order.customer_code} name={order.customer_name} /></td>
                <td>{formatDateTime(order.created_at)}</td>
                <td className="mono-data">{formatCurrency(order.total_value)}</td>
                <td style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  {order.line_item_count}
                  {order.failed_line_count > 0 && (
                    <span style={{ color: '#ef4444', marginLeft: 4 }}>
                      ({order.failed_line_count} ✕)
                    </span>
                  )}
                </td>
                <td><StatusBadge status={order.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>

        {recent_orders.length === 0 && (
          <div className="empty-state">
            <Package size={40} className="empty-state-icon" />
            <div style={{ fontSize: 14, fontWeight: 600 }}>No orders yet</div>
            <div style={{ fontSize: 12 }}>Orders will appear here once the email ingestion begins</div>
          </div>
        )}
      </div>
    </div>
  )
}