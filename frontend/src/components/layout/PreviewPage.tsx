import { ArrowRight, CircleDashed, LockKeyhole } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '../ui/Badge'
import { Card } from '../ui/Card'
import { PageHeader } from './PageHeader'

export function PreviewPage({ eyebrow, title, description, capability, nextPath, nextLabel }: { eyebrow: string; title: string; description: string; capability: string; nextPath?: string; nextLabel?: string }) {
  return <div className="page-stack preview-page" data-testid="preview-page"><PageHeader eyebrow={eyebrow} title={title} description={description} breadcrumbs={[{ label: '题伴', to: '/' }, { label: title }]} /><Card className="preview-hero"><div className="preview-icon"><CircleDashed size={26} /></div><Badge tone="amber">界面预览 · 尚未接入</Badge><h2>{capability}</h2><p>这一入口用于展示 V3 的能力边界和后续接入位置。当前没有真实数据返回，也不会生成虚构的指标、来源或审计状态。</p><div className="preview-boundary"><LockKeyhole size={16} /><span>尚未运行 · 不展示模型连接成功、评测数字、来源证据或临床结论。</span></div>{nextPath && <Link className="ui-button ui-button-secondary ui-button-md" to={nextPath}>{nextLabel ?? '回到核心工作台'}<ArrowRight size={16} /></Link>}</Card></div>
}
