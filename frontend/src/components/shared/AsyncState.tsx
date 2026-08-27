import { AlertCircle, LoaderCircle } from 'lucide-react'

export function LoadingState({ label = '正在读取真实数据…' }: { label?: string }) {
  return <div className="s1-state" role="status"><LoaderCircle className="s1-spin" size={22} /><span>{label}</span></div>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="s1-state s1-state-error" role="alert">
      <AlertCircle size={22} />
      <div><strong>暂时无法读取数据</strong><span>{message}</span></div>
      <button className="s1-button s1-button-light" onClick={onRetry}>重试</button>
    </div>
  )
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="s1-empty"><strong>{title}</strong><span>{detail}</span></div>
}
