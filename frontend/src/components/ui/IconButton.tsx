import type { ButtonHTMLAttributes, ReactNode } from 'react'

export function IconButton({
  label,
  children,
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; children: ReactNode }) {
  return <button className={`ui-icon-button ${className}`.trim()} aria-label={label} {...props}>{children}</button>
}
