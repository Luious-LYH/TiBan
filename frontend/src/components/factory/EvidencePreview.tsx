import { Link2 } from 'lucide-react'

export function EvidencePreview({ sourceChunkIds }: { sourceChunkIds: string[] }) {
  if (sourceChunkIds.length === 0) return <div className="factory-evidence is-empty"><Link2 size={14} /><span>尚未返回关联资料片段</span></div>
  return <div className="factory-evidence"><Link2 size={14} /><div><strong>已关联 {sourceChunkIds.length} 条资料片段</strong><small>生成与审核时可依据这些资料片段追溯来源。</small></div></div>
}
