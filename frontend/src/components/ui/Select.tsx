import type { SelectHTMLAttributes } from 'react'

export type SelectOption = { value: string; label: string }

export function Select({ label, options, className = '', ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label?: string; options: SelectOption[] }) {
  return (
    <label className={`ui-field ${className}`.trim()}>
      {label && <span>{label}</span>}
      <select {...props}>{options.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select>
    </label>
  )
}
