import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'

type CardProps = HTMLAttributes<HTMLElement> & {
  children: ReactNode
}

export const Card = forwardRef<HTMLElement, CardProps>(function Card({ children, className = '', ...props }, ref) {
  return <section ref={ref} {...props} className={`card ${className}`}>{children}</section>
})

export function SectionTitle({
  eyebrow,
  title,
  action,
}: {
  eyebrow?: string
  title: string
  action?: ReactNode
}) {
  return (
    <div className="section-title">
      <div>
        {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
        <h2>{title}</h2>
      </div>
      {action}
    </div>
  )
}

export function Tag({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'green' | 'amber' | 'red' | 'blue' }) {
  return <span className={`tag tag-${tone}`}>{children}</span>
}

export function SafetyNotice({ text }: { text: string }) {
  return (
    <div className="safety-strip">
      <strong>安全边界</strong>
      <span>{text}</span>
    </div>
  )
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>
}
