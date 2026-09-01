export function Skeleton({ className = '' }: { className?: string }) {
  return <span className={`ui-skeleton ${className}`.trim()} aria-hidden="true" />
}
