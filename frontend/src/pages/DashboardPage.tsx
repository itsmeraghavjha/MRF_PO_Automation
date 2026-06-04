import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TrendingUp, Package, AlertOctagon, CheckCircle2, Zap, ArrowUpRight, RefreshCw } from 'lucide-react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import { getDashboard, type DashboardResponse } from '../services/api'
import { StatusBadge, formatCurrency, formatRelativeTime, CustomerChip } from '../components/shared/StatusBadge'

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
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <div className="spinner" style={{ width: 24, height: 24 }} />
      </div>
    )
  }

  const { kpis, status_breakdown, recent_orders } = data!

  const metrics = [
    {
      label: 'Orders Today',
      value: kpis.total_pos_today,
      sub: `${kpis.total_pos_all_time} total`,
      icon: Package,
      color: '#4f8ef7',
    },
    {
      label: 'Value Today',
      value: formatCurrency(kpis.total_value_today),
      sub: `${formatCurrency(kpis.total_value_all_time)} all-time`,
      icon: TrendingUp,
      color: '#10b981',
    },
    {
      label: 'Auto-Processed',
      value: kpis.auto_processed,
      sub: `${kpis.success_rate}% success rate`,
      icon: Zap,
      color: '#1E6B3C',
    },
    {
      label: 'Exceptions',
      value: kpis.exceptions_pending,
      sub: 'Pending review',
      icon: AlertOctagon,
      color: kpis.exceptions_pending > 0 ? '#C8272D' : '#10b981',
      urgent: kpis.exceptions_pending > 0,
    },
    {
      label: 'SAP Pushed',
      value: kpis.sap_pushed,
      sub: 'Orders in SAP',
      icon: CheckCircle2,
      color: '#1D6FA4',
    },
  ]

  return (
    <div style={{ padding: '20px' }} className="animate-fade">
      {/* Page Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 1 }}>
            Operations Dashboard
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: 11 }}>
            Live PO status · auto-refreshes every 10s
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {lastRefresh.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
          <button className="btn btn-ghost btn-icon" onClick={load}><RefreshCw size={12} /></button>
        </div>
      </div>

      {/* ── KPI Metric Strip ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginBottom: 14 }}>
        {metrics.map(({ label, value, sub, icon: Icon, color, urgent }) => (
          <div
            key={label}
            className="card"
            style={{
              padding: '24px',
              borderColor: urgent ? 'rgba(200,39,45,0.25)' : 'var(--border)',
              position: 'relative', overflow: 'hidden',
            }}
          >
            <div style={{
              position: 'absolute', top: 0, right: 0,
              width: 56, height: 56,
              background: `radial-gradient(circle at 100% 0%, ${color}18 0%, transparent 70%)`,
              pointerEvents: 'none'
            }} />
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 500 }}>{label}</span>
              <div style={{
                width: 24, height: 24, borderRadius: 6,
                background: `${color}15`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon size={13} color={color} />
              </div>
            </div>
            <div style={{
  fontFamily: 'var(--font-display)', /* Binds to Syne */
  fontSize: 32, /* Scaled up to fill the card */
  fontWeight: 700,
  color: urgent ? '#C8272D' : 'var(--text-primary)',
  lineHeight: 1, marginBottom: 4, letterSpacing: '-0.02em'
}}>
              {value}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{sub}</div>
          </div>
        ))}
      </div>

      {/* ── Middle Row: Chart + Breakdown ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 24, marginBottom: 24 }}>
        {/* Status breakdown */}
        <div className="card" style={{ padding: '12px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>Status Distribution</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>All time</span>
          </div>
          <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
            <ResponsiveContainer width={130} height={130}>
              <PieChart>
                <Pie
                  data={status_breakdown}
                  cx="50%" cy="50%"
                  innerRadius={40} outerRadius={62}
                  paddingAngle={2}
                  dataKey="count"
                >
                  {status_breakdown.map((entry) => (
                    <Cell key={entry.status} fill={entry.color} stroke="transparent" />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                    borderRadius: 7, fontSize: 11, padding: '6px 10px'
                  }}
                  formatter={(v, _, { payload }) => [v, payload.label]}
                />
              </PieChart>
            </ResponsiveContainer>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
              {status_breakdown.map((s) => (
                <div key={s.status} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '3px 0'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                    <div style={{ width: 7, height: 7, borderRadius: 2, background: s.color, flexShrink: 0 }} />
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{s.label}</span>
                  </div>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, color: s.color }}>
                    {s.count}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Success Rate */}
        <div className="card" style={{
          padding: '24px',
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', textAlign: 'center', gap: 6,
          position: 'relative', overflow: 'hidden'
        }}>
          <div style={{
            position: 'absolute', inset: 0,
            background: `conic-gradient(
              #1E6B3C 0deg ${kpis.success_rate * 3.6}deg,
              rgba(30,107,60,0.05) ${kpis.success_rate * 3.6}deg 360deg
            )`,
            borderRadius: 'var(--radius-lg)',
            mask: 'radial-gradient(farthest-side, transparent 62%, black 63%)',
            WebkitMask: 'radial-gradient(farthest-side, transparent 62%, black 63%)',
          }} />
          <CheckCircle2 size={16} color="#1E6B3C" />
          <div style={{ fontSize: 32, fontWeight: 900, color: '#1E6B3C', lineHeight: 1, letterSpacing: '-0.03em' }}>
            {kpis.success_rate}%
          </div>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>Auto-Process Rate</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {kpis.sap_pushed}/{kpis.total_pos_all_time} orders
          </div>
        </div>
      </div>

      {/* ── Recent Orders Table ── */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '10px 14px', borderBottom: '1px solid var(--border)'
        }}>
          <span style={{ fontSize: 12, fontWeight: 600 }}>Recent Orders</span>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => navigate('/orders')}
            style={{ display: 'flex', alignItems: 'center', gap: 3 }}
          >
            View all <ArrowUpRight size={11} />
          </button>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>PO Number</th>
              <th>Customer</th>
              <th>Received</th>
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
                <td style={{ color: 'var(--text-muted)', fontSize: 11 }}>{formatRelativeTime(order.created_at)}</td>
                <td className="mono-data">{formatCurrency(order.total_value)}</td>
                <td style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                  {order.line_item_count}
                  {order.failed_line_count > 0 && (
                    <span style={{ color: '#C8272D', marginLeft: 3 }}>({order.failed_line_count}✕)</span>
                  )}
                </td>
                <td><StatusBadge status={order.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {recent_orders.length === 0 && (
          <div className="empty-state">
            <Package size={32} className="empty-state-icon" />
            <div style={{ fontSize: 13, fontWeight: 600 }}>No orders yet</div>
            <div style={{ fontSize: 11 }}>Orders appear once email ingestion begins</div>
          </div>
        )}
      </div>
    </div>
  )
}