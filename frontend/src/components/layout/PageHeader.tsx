import type { ReactNode } from 'react'
import { Breadcrumbs } from './Breadcrumbs'

export function PageHeader({ eyebrow, title, description, breadcrumbs, actions }: { eyebrow?: string; title: string; description?: string; breadcrumbs?: Array<{ label: string; to?: string }>; actions?: ReactNode }) {
  return <header className="page-header">{breadcrumbs && <Breadcrumbs items={breadcrumbs} />}<div className="page-header-row"><div>{eyebrow && <span className="page-eyebrow">{eyebrow}</span>}<h1>{title}</h1>{description && <p>{description}</p>}</div>{actions && <div className="page-header-actions">{actions}</div>}</div></header>
}
