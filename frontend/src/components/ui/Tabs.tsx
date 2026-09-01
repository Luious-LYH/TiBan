import type { ReactNode } from 'react'

export type TabItem = { value: string; label: string; icon?: ReactNode }

export function Tabs({ items, value, onChange, label = '页面分区' }: { items: TabItem[]; value: string; onChange: (value: string) => void; label?: string }) {
  return (
    <div className="ui-tabs" role="tablist" aria-label={label}>
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          role="tab"
          aria-selected={item.value === value}
          className={item.value === value ? 'is-active' : ''}
          onClick={() => onChange(item.value)}
        >
          {item.icon}
          {item.label}
        </button>
      ))}
    </div>
  )
}
