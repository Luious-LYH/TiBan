import { AlertTriangle, LoaderCircle, X } from 'lucide-react'
import { useEffect, useRef } from 'react'

type EvaluationType = 'model' | 'rag'

interface EvaluationConfirmDialogProps {
  open: boolean
  bankName: string
  evaluationType: EvaluationType
  pending?: boolean
  error?: string | null
  onCancel: () => void
  onConfirm: () => void
}

export function EvaluationConfirmDialog({
  open,
  bankName,
  evaluationType,
  pending = false,
  error,
  onCancel,
  onConfirm,
}: EvaluationConfirmDialogProps) {
  const cancelButton = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    cancelButton.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !pending) onCancel()
    }
    document.addEventListener('keydown', onKeyDown)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [onCancel, open, pending])

  if (!open) return null

  const typeLabel = evaluationType === 'model' ? '模型评测' : 'RAG 评测'
  return <div
    className="evaluation-confirm-backdrop"
    role="presentation"
    onMouseDown={(event) => {
      if (event.target === event.currentTarget && !pending) onCancel()
    }}
  >
    <section className="evaluation-confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="evaluation-confirm-title" aria-describedby="evaluation-confirm-description">
      <header className="evaluation-confirm-header">
        <div className="evaluation-confirm-icon"><AlertTriangle size={20} /></div>
        <button type="button" className="evaluation-confirm-close" aria-label="关闭确认弹窗" onClick={onCancel} disabled={pending}><X size={17} /></button>
      </header>
      <div className="evaluation-confirm-body">
        <span className="evaluation-confirm-eyebrow">{typeLabel} · 重新准备题目</span>
        <h2 id="evaluation-confirm-title">重新抽样评测集？</h2>
        <p id="evaluation-confirm-description">将为「{bankName}」重新抽取一批题目。当前 {typeLabel} 的历史评测结果会被删除，然后从新的题目集合开始；评测集记录本身会保留。</p>
        <div className="evaluation-confirm-note"><span>影响范围</span><strong>仅当前题库的 {typeLabel}</strong><small>其它题库和另一种评测类型的结果不会受到影响。</small></div>
        {error && <p className="evaluation-confirm-error" role="alert">{error}</p>}
      </div>
      <footer className="evaluation-confirm-actions">
        <button ref={cancelButton} type="button" className="evaluation-confirm-cancel" onClick={onCancel} disabled={pending}>取消</button>
        <button type="button" className="evaluation-confirm-submit" onClick={onConfirm} disabled={pending}>
          {pending && <LoaderCircle size={15} className="s1-spin" />}
          {pending ? '正在重新准备…' : '确认重新抽样'}
        </button>
      </footer>
    </section>
  </div>
}
