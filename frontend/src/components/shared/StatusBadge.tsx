import React from 'react'
import { CheckCircle2, AlertTriangle, Clock, Loader2, CheckCheck, HelpCircle } from 'lucide-react'


const STATUS_CONFIG: Record<string, {
  label: string; cls: string; Icon: React.ComponentType<{ size?: number }>;
}> = {
  NEW:                    { label: 'Processing',     cls: 'badge-new',       Icon: Loader2 },
  VALIDATED:              { label: 'Ready for SAP',  cls: 'badge-validated', Icon: CheckCircle2 },
  VALIDATION_FAILED:      { label: 'Needs Review',   cls: 'badge-failed',    Icon: AlertTriangle },
  AWAITING_DELIVERY_DATE: { label: 'Awaiting Date',  cls: 'badge-awaiting',  Icon: Clock },
  SAP_SUCCESS:            { label: 'SAP Pushed',      cls: 'badge-sap',       Icon: CheckCheck },
}

export function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] || { label: status, cls: '', Icon: HelpCircle }
  const { Icon, label, cls } = cfg
  return (
    <span className={`badge ${cls}`}>
      <Icon size={10} />
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
  } catch {
    return dateStr
  }
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    return d.toLocaleString('en-IN', {
      day: '2-digit', month: 'short',
      hour: '2-digit', minute: '2-digit', hour12: true
    })
  } catch {
    return dateStr
  }
}

export function CustomerChip({ code, name }: { code?: string | null, name?: string | null }) {
  const colors: Record<string, string> = {
    RRL: '#6366f1', DMT: '#10b981', BBK: '#f59e0b',
    ZEP: '#8b5cf6', AMZ: '#3b82f6', WMT: '#0ea5e9',
  }
  const color = colors[code || ''] || '#6b7280'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: 22, height: 22, borderRadius: 4,
        background: `${color}22`, color,
        fontSize: 9, fontWeight: 800, fontFamily: 'var(--font-mono)',
        flexShrink: 0
      }}>
        {code?.slice(0, 3) || '?'}
      </span>
      <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
        {name || code || '—'}
      </span>
    </div>
  )
}