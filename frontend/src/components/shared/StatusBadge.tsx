import React from 'react'
import { CheckCircle2, AlertTriangle, Clock, Loader2, CheckCheck, HelpCircle, LucideProps } from 'lucide-react'

type LucideIcon = React.ForwardRefExoticComponent<Omit<LucideProps, "ref"> & React.RefAttributes<SVGSVGElement>>

const STATUS_CONFIG: Record<string, { label: string; cls: string; Icon: LucideIcon }> = {
  NEW:                    { label: 'Processing',    cls: 'badge-new',       Icon: Loader2      },
  VALIDATED:              { label: 'Ready',         cls: 'badge-validated', Icon: CheckCircle2 },
  VALIDATION_FAILED:      { label: 'Needs Review',  cls: 'badge-failed',    Icon: AlertTriangle},
  AWAITING_DELIVERY_DATE: { label: 'Awaiting Date', cls: 'badge-awaiting',  Icon: Clock        },
  SAP_SUCCESS:            { label: 'SAP Pushed',    cls: 'badge-sap',       Icon: CheckCheck   },
}

export function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] || { label: status, cls: '', Icon: HelpCircle }
  const { Icon, label, cls } = cfg
  return (
    <span className={`badge ${cls}`}>
      <Icon size={9} />
      {label}
    </span>
  )
}

export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return '—'
  return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
  } catch { return dateStr }
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    return d.toLocaleString('en-IN', {
      day: '2-digit', month: 'short',
      hour: '2-digit', minute: '2-digit', hour12: true
    })
  } catch { return dateStr }
}

export function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  try {
    const diff = Date.now() - new Date(dateStr).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1)  return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24)  return `${hrs}h ago`
    const days = Math.floor(hrs / 24)
    return `${days}d ago`
  } catch { return dateStr }
}

const CUSTOMER_COLORS: Record<string, string> = {
  RRL: '#6366f1', DMT: '#10b981', BBK: '#f59e0b',
  ZEP: '#8b5cf6', AMZ: '#3b82f6', WMT: '#0ea5e9',
}

export function CustomerChip({ code, name }: { code?: string | null; name?: string | null }) {
  const color = CUSTOMER_COLORS[code || ''] || '#6b7280'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: 20, height: 20, borderRadius: 4,
        background: `${color}1A`, color,
        fontSize: 9, fontWeight: 800, fontFamily: 'var(--font-mono)',
        flexShrink: 0, letterSpacing: '0.02em'
      }}>
        {code?.slice(0, 3) || '?'}
      </span>
      <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
        {name || code || '—'}
      </span>
    </div>
  )
}