import { X } from 'lucide-react'
import { useEffect, useRef, useState, type DragEvent, type ClipboardEvent, type ReactNode } from 'react'

const maxChatImageBytes = 8 * 1024 * 1024

type ImageAttachmentProps = {
  file: File | null
  onChange: (file: File | null) => void
  disabled?: boolean
  children: ReactNode
  className?: string
}

/** A deliberately small, chooser-free image affordance for Tutor/Mentor. */
export function ImageAttachment({ file, onChange, disabled = false, children, className = '' }: ImageAttachmentProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const previewRef = useRef<string | null>(null)

  useEffect(() => {
    return () => {
      if (previewRef.current) URL.revokeObjectURL(previewRef.current)
    }
  }, [])

  useEffect(() => {
    if (!file && previewRef.current) {
      URL.revokeObjectURL(previewRef.current)
      previewRef.current = null
    }
  }, [file])

  function accept(fileCandidate?: File) {
    if (!fileCandidate || disabled) return
    if (!fileCandidate.type.startsWith('image/')) {
      setError('这里只能附加图片。')
      return
    }
    if (fileCandidate.size > maxChatImageBytes) {
      setError('图片不能超过 8 MiB。')
      return
    }
    setError(null)
    if (previewRef.current) URL.revokeObjectURL(previewRef.current)
    previewRef.current = URL.createObjectURL(fileCandidate)
    setPreviewUrl(previewRef.current)
    onChange(fileCandidate)
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    accept(event.dataTransfer.files?.[0])
  }

  function onPaste(event: ClipboardEvent<HTMLDivElement>) {
    const image = Array.from(event.clipboardData.files).find((item) => item.type.startsWith('image/'))
      ?? Array.from(event.clipboardData.items)
        .find((item) => item.kind === 'file' && item.type.startsWith('image/'))
        ?.getAsFile()
    if (image) {
      event.preventDefault()
      accept(image)
    }
  }

  return <div className={`image-attachment ${className}`} onDragOver={(event) => event.preventDefault()} onDrop={onDrop} onPaste={onPaste}>
    {file && previewUrl && <div className="image-attachment-preview"><img src={previewUrl} alt="待发送的图片" /><div><strong>{file.name || '已附加图片'}</strong><small>发送前可移除</small></div><button type="button" aria-label="移除图片" title="移除图片" disabled={disabled} onClick={() => { setError(null); if (previewRef.current) URL.revokeObjectURL(previewRef.current); previewRef.current = null; setPreviewUrl(null); onChange(null) }}><X size={14} /></button></div>}
    {children}
    {error && <p className="image-attachment-error" role="alert">{error}</p>}
  </div>
}
