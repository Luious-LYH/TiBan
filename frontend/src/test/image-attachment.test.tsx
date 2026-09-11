import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useState } from 'react'

import { ImageAttachment } from '../components/shared/ImageAttachment'

function ControlledAttachment({ onChange }: { onChange: (file: File | null) => void }) {
  const [file, setFile] = useState<File | null>(null)
  return <ImageAttachment file={file} onChange={(next) => { setFile(next); onChange(next) }}><textarea aria-label="消息" /></ImageAttachment>
}

describe('ImageAttachment', () => {
  beforeEach(() => {
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:test-image'),
      revokeObjectURL: vi.fn(),
    })
  })

  function pasteImage(target: HTMLElement, file: File, viaItems = false) {
    const event = new Event('paste', { bubbles: true })
    Object.defineProperty(event, 'clipboardData', {
      value: viaItems
        ? { files: { length: 0 }, items: [{ kind: 'file', type: 'image/png', getAsFile: () => file }] }
        : { files: { 0: file, length: 1 }, items: [] },
    })
    target.dispatchEvent(event)
  }

  it('accepts a pasted image exposed through clipboard items', () => {
    const onChange = vi.fn()
    const file = new File(['png'], '观察图.png', { type: 'image/png' })
    render(<ControlledAttachment onChange={onChange} />)

    const event = new Event('paste', { bubbles: true })
    Object.defineProperty(event, 'clipboardData', {
      value: { files: { length: 0 }, items: [{ kind: 'file', type: 'image/png', getAsFile: () => file }] },
    })
    screen.getByRole('textbox', { name: '消息' }).dispatchEvent(event)

    expect(onChange).toHaveBeenCalledWith(file)
    return waitFor(() => expect(screen.getByText('观察图.png')).toBeInTheDocument())
  })

  it('keeps the composer chooser-free and removes an attached image', () => {
    const onChange = vi.fn()
    const file = new File(['png'], 'image.png', { type: 'image/png' })
    const { container } = render(<ControlledAttachment onChange={onChange} />)

    pasteImage(container.firstElementChild as HTMLElement, file)

    expect(screen.queryByRole('button', { name: /选择图片|上传图片/ })).not.toBeInTheDocument()
    return waitFor(() => expect(screen.getByRole('button', { name: '移除图片' })).toBeInTheDocument()).then(() => {
      fireEvent.click(screen.getByRole('button', { name: '移除图片' }))
    expect(onChange).toHaveBeenCalledWith(null)
    expect(screen.queryByText('可将图片拖到这里，或直接粘贴')).not.toBeInTheDocument()
    })
  })
})
