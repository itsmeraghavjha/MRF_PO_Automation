import { useState } from 'react'
import { Send, Clock, CheckCircle2, ExternalLink, RefreshCw } from 'lucide-react'

interface DeliveryRequestButtonProps {
  orderId: number
  orderStatus: string
  deliveryDate: string | null
  onSuccess: () => void
}

interface TokenStatus {
  token: string
  recipient_email: string
  status: 'PENDING' | 'VISITED' | 'UPDATED' | 'EXPIRED'
  expires_at: string
  portal_url?: string
  current_delivery_date: string | null
}

export function DeliveryRequestButton({
  orderId,
  orderStatus,
  deliveryDate,
  onSuccess,
}: DeliveryRequestButtonProps) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{
    success: boolean
    recipient?: string
    email_sent?: boolean
    portal_url?: string
    token?: string
    error?: string
  } | null>(null)

  const canSend = ['VALIDATED', 'SAP_SUCCESS', 'AWAITING_DELIVERY_DATE'].includes(orderStatus)

  const handleSend = async () => {
    setLoading(true)
    try {
      const res = await fetch(`/api/v1/orders/${orderId}/send-delivery-request`, {
        method: 'POST',
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Request failed')
      setResult({ success: true, ...data })
      onSuccess()
    } catch (e: any) {
      setResult({ success: false, error: e.message })
    } finally {
      setLoading(false)
    }
  }

  if (!canSend) return null

  return (
    <div>
      {!result ? (
        <button
          className="btn btn-secondary btn-sm"
          onClick={handleSend}
          disabled={loading}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          {loading ? (
            <span className="spinner" style={{ width: 12, height: 12 }} />
          ) : (
            <Send size={13} />
          )}
          {loading ? 'Sending…' : 'Send Delivery Request'}
        </button>
      ) : result.success ? (
        <div style={{
          background: 'rgba(16,185,129,0.08)',
          border: '1px solid rgba(16,185,129,0.2)',
          borderRadius: 8,
          padding: '10px 14px',
          fontSize: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#10b981', fontWeight: 600, marginBottom: 4 }}>
            <CheckCircle2 size={13} />
            {result.email_sent ? 'Confirmation email sent' : 'Token generated (SMTP not configured — check logs)'}
          </div>
          <div style={{ color: 'var(--text-muted)', marginBottom: 6 }}>
            Recipient: <span style={{ color: 'var(--text-secondary)' }}>{result.recipient}</span>
          </div>
          {result.portal_url && (
            <a
              href={result.portal_url}
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                color: 'var(--accent-blue)', fontSize: 11,
              }}
            >
              <ExternalLink size={10} /> Preview vendor portal
            </a>
          )}
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setResult(null)}
            style={{ marginLeft: 8, fontSize: 11 }}
          >
            <RefreshCw size={10} /> Resend
          </button>
        </div>
      ) : (
        <div style={{
          background: 'rgba(239,68,68,0.08)',
          border: '1px solid rgba(239,68,68,0.2)',
          borderRadius: 8,
          padding: '10px 14px',
          fontSize: 12,
          color: '#ef4444',
        }}>
          {result.error}
          <button className="btn btn-ghost btn-sm" onClick={() => setResult(null)} style={{ marginLeft: 8 }}>
            Retry
          </button>
        </div>
      )}
    </div>
  )
}


// ── Token status badge — shows in order detail audit area ─────────────────

const TOKEN_STATUS_CONFIG = {
  PENDING:  { label: 'Email Sent — Awaiting Response', color: '#f59e0b', bg: 'rgba(245,158,11,0.1)' },
  VISITED:  { label: 'Link Opened by Vendor',          color: '#3b82f6', bg: 'rgba(59,130,246,0.1)' },
  UPDATED:  { label: 'Delivery Date Confirmed',        color: '#10b981', bg: 'rgba(16,185,129,0.1)' },
  EXPIRED:  { label: 'Link Expired',                   color: '#6b7280', bg: 'rgba(107,114,128,0.1)' },
}

export function DeliveryTokenStatus({ orderId }: { orderId: number }) {
  const [status, setStatus] = useState<TokenStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [checked, setChecked] = useState(false)

  const check = async () => {
    setLoading(true)
    try {
      // We'd need the token — for now show the order's delivery status via audit logs
      // This is a lightweight poll-by-order approach
      setChecked(true)
    } finally {
      setLoading(false)
    }
  }

  return null // Audit logs in OrderDetail already show the DELIVERY_REQUEST_SENT event
}