import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Inbox, AlertTriangle, Database,
  ChevronRight, Zap
} from 'lucide-react'

const NAV = [
  { to: '/',         icon: LayoutDashboard, label: 'Dashboard',       desc: 'Live operations view'   },
  { to: '/orders',   icon: Inbox,           label: 'Orders',          desc: 'All POs & status'       },
  { to: '/exceptions', icon: AlertTriangle, label: 'Exception Queue', desc: 'Needs manual review', badge: true },
  { to: '/master-data', icon: Database,     label: 'Master Data',     desc: 'Products, prices, maps' },
]

export default function Sidebar({ exceptionCount }: { exceptionCount: number }) {
  return (
    <aside className="sidebar">
      {/* Brand */}
      <div style={{ padding: '20px 20px 16px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 8,
            background: 'linear-gradient(135deg, var(--accent-amber), #c97d20)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0, boxShadow: '0 2px 8px rgba(226,168,75,0.3)'
          }}>
            <Zap size={16} color="#0a0f1a" />
          </div>
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 14, letterSpacing: '-0.01em', lineHeight: 1.2 }}>
              Heritage Foods
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', fontWeight: 600 }}>
              PO Automation
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ padding: '12px 10px', flex: 1 }}>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.1em', textTransform: 'uppercase', fontWeight: 700, padding: '0 8px', marginBottom: 8 }}>
          Platform
        </div>
        {NAV.map(({ to, icon: Icon, label, desc, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '9px 10px',
              borderRadius: 8,
              textDecoration: 'none',
              marginBottom: 2,
              transition: 'all 0.15s',
              background: isActive ? 'var(--bg-elevated)' : 'transparent',
              borderLeft: isActive ? '2px solid var(--accent-amber)' : '2px solid transparent',
              paddingLeft: 8,
            })}
          >
            {({ isActive }) => (
              <>
                <Icon
                  size={16}
                  color={isActive ? 'var(--accent-amber)' : 'var(--text-muted)'}
                  style={{ flexShrink: 0 }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 13, fontWeight: 500,
                    color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                    lineHeight: 1.3
                  }}>
                    {label}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.2 }}>
                    {desc}
                  </div>
                </div>
                {badge && exceptionCount > 0 && (
                  <span style={{
                    background: 'var(--status-failed)',
                    color: 'white',
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '1px 6px',
                    borderRadius: 10,
                    minWidth: 18,
                    textAlign: 'center'
                  }}>
                    {exceptionCount}
                  </span>
                )}
                {isActive && (
                  <ChevronRight size={12} color="var(--text-muted)" style={{ flexShrink: 0 }} />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)' }}>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
          v1.0.0 · Phase 1
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
          HFL-AUTO-BRD-001
        </div>
      </div>
    </aside>
  )
}