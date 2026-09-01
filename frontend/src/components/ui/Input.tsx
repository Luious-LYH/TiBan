import type { InputHTMLAttributes } from 'react'

export function Input({ label, hint, className = '', ...props }: InputHTMLAttributes<HTMLInputElement> & { label?: string; hint?: string }) {
  return (
    <label className={`ui-field ${className}`.trim()}>
      {label && <span>{label}{hint && <small>{hint}</small>}</span>}
      <input {...props} />
    </label>
  )
}
