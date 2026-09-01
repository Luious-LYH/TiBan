import type { ReactNode } from 'react'

type BadgeTone = 'neutral' | 'teal' | 'blue' | 'amber' | 'red'

export function Badge({ children, tone = 'neutral', className = '' }: { children: ReactNode; tone?: BadgeTone; className?: string }) {
  return <span className={`ui-badge ui-badge-${tone} ${className}`.trim()}>{children}</span>
}
