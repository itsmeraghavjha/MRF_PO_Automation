import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Inbox, AlertTriangle, Database,
  Zap, PanelLeftClose, PanelLeft
} from 'lucide-react'

const NAV = [
  { to: '/',            icon: LayoutDashboard, label: 'Dashboard',       badge: false },
  { to: '/orders',      icon: Inbox,           label: 'Orders',          badge: false },
  { to: '/exceptions',  icon: AlertTriangle,   label: 'Exceptions',      badge: true  },
  { to: '/master-data', icon: Database,        label: 'Master Data',     badge: false },
]

export default function Sidebar({
  exceptionCount,
  isCollapsed,
  setIsCollapsed
}: {
  exceptionCount: number
  isCollapsed: boolean
  setIsCollapsed: (v: boolean) => void
}) {
  return (
    <aside className="sidebar">
      {/* Brand */}
      <div style={{
        padding: isCollapsed ? '14px 0' : '14px 12px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: isCollapsed ? 'center' : 'space-between',
        gap: 8,
        minHeight: 52,
      }}>
        {!isCollapsed && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 28, height: 28, borderRadius: 7,
              background: 'linear-gradient(135deg, #2A8A4F, #1E6B3C)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0, boxShadow: '0 2px 6px rgba(30,107,60,0.4)'
            }}>
              <Zap size={14} color="#fff" />
            </div>
            <div>
              <div style={{
                fontWeight: 700, fontSize: 13, color: '#fff',
                letterSpacing: '-0.01em', lineHeight: 1.2
              }}>Heritage Foods</div>
              <div style={{
                fontSize: 10, color: 'rgba(255,255,255,0.4)',
                letterSpacing: '0.06em', textTransform: 'uppercase', fontWeight: 600
              }}>PO Automation</div>
            </div>
          </div>
        )}
        {isCollapsed && (
          <div style={{
            width: 28, height: 28, borderRadius: 7,
            background: 'linear-gradient(135deg, #2A8A4F, #1E6B3C)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 2px 6px rgba(30,107,60,0.4)'
          }}>
            <Zap size={14} color="#fff" />
          </div>
        )}
      </div>

      {/* Nav */}
      <nav style={{ padding: '8px 6px', flex: 1 }}>
        {!isCollapsed && (
          <div style={{
            fontSize: 10, color: 'rgba(255,255,255,0.25)',
            letterSpacing: '0.1em', textTransform: 'uppercase',
            fontWeight: 700, padding: '0 6px', marginBottom: 4
          }}>
            Navigation
          </div>
        )}
        {NAV.map(({ to, icon: Icon, label, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            title={isCollapsed ? label : undefined}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              position: 'relative',
              gap: 8,
              padding: isCollapsed ? '7px 0' : '6px 8px',
              borderRadius: 7,
              textDecoration: 'none',
              marginBottom: 1,
              transition: 'all 0.12s',
              background: isActive ? 'rgba(30,107,60,0.28)' : 'transparent',
              borderLeft: isActive ? '2px solid #4CAF73' : '2px solid transparent',
              justifyContent: isCollapsed ? 'center' : 'flex-start',
            })}
          >
            {({ isActive }) => (
              <>
                <Icon
                  size={15}
                  color={isActive ? '#6BD48A' : 'rgba(255,255,255,0.4)'}
                  style={{ flexShrink: 0 }}
                />
                {!isCollapsed && (
                  <>
                    <span style={{
                      flex: 1,
                      fontSize: 13,
                      fontWeight: isActive ? 600 : 400,
                      color: isActive ? '#fff' : 'rgba(255,255,255,0.55)',
                      lineHeight: 1,
                    }}>
                      {label}
                    </span>
                    {badge && exceptionCount > 0 && (
                      <span style={{
                        background: '#C8272D', color: 'white',
                        fontSize: 10, fontWeight: 700,
                        padding: '1px 5px', borderRadius: 10,
                        minWidth: 16, textAlign: 'center', lineHeight: 1.6
                      }}>
                        {exceptionCount}
                      </span>
                    )}
                  </>
                )}
                {isCollapsed && badge && exceptionCount > 0 && (
                  <span style={{
                    position: 'absolute', top: 4, right: 6,
                    width: 7, height: 7, borderRadius: '50%',
                    background: '#C8272D', border: '1.5px solid #0E1712'
                  }} />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div style={{
        padding: isCollapsed ? '10px 0' : '10px 12px',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: isCollapsed ? 'center' : 'space-between',
      }}>
        {!isCollapsed && (
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)', letterSpacing: '0.04em' }}>
            v1.0 · Phase 1
          </span>
        )}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            color: 'rgba(255,255,255,0.3)', display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            padding: 4, borderRadius: 5, transition: 'color 0.12s',
          }}
          onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.7)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.3)')}
          title={isCollapsed ? 'Expand' : 'Collapse'}
        >
          {isCollapsed ? <PanelLeft size={14} /> : <PanelLeftClose size={14} />}
        </button>
      </div>
    </aside>
  )
}