import { AlertCircle, CheckCircle2, Info, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'

type StatusTone = 'info' | 'success' | 'warning' | 'error' | 'loading'

const icons = { info: Info, success: CheckCircle2, warning: AlertCircle, error: AlertCircle, loading: LoaderCircle }

export function StatusMessage({ tone = 'info', title, children, action }: { tone?: StatusTone; title?: string; children: ReactNode; action?: ReactNode }) {
  const Icon = icons[tone]
  return <div className={`ui-status ui-status-${tone}`} role={tone === 'error' ? 'alert' : 'status'}><Icon size={16} className={tone === 'loading' ? 'ui-spin' : undefined} /><div>{title && <strong>{title}</strong>}<span>{children}</span></div>{action}</div>
}
