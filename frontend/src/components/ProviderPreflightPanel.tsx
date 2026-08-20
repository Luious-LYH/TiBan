import { AlertTriangle, LoaderCircle, ShieldCheck } from 'lucide-react'
import { Tag } from './Primitives'
import type { ProviderPreflight } from '../lib/types'

export function ProviderPreflightPanel({
  preflight,
  loading,
}: {
  preflight: ProviderPreflight | null
  loading: boolean
}) {
  const fallback = preflight?.api_source === 'fallback'
  const ok = Boolean(preflight?.ok)
  const statusTone: 'red' | 'green' | 'amber' = fallback ? 'red' : ok ? 'green' : 'amber'

  return (
    <div className={`provider-preflight-panel ${fallback ? 'fallback' : ok ? 'synced' : 'blocked'}`}>
      <div className="provider-preflight-head">
        {loading ? <LoaderCircle className="spin-icon" size={19} /> : ok ? <ShieldCheck size={19} /> : <AlertTriangle size={19} />}
        <div>
          <span className="eyebrow">接口安全预检</span>
          <strong>{loading ? '正在检查连接入口安全策略' : ok ? '连接入口可进入智能服务调用流程' : '连接入口暂不能进入智能服务调用'}</strong>
          <p>预检只做连接规范、安全策略和调用路径推导，不发送模型请求、不读取或保存一次性授权。</p>
        </div>
        <Tag tone={statusTone}>{statusLabel(preflight?.safety_status)}</Tag>
      </div>
      {preflight ? (
        <>
          <div className="provider-preflight-grid">
            <div><span>模式</span><strong>{preflight.mode}</strong></div>
            <div><span>规范化预览</span><strong>{preflight.normalized_preview || '未配置'}</strong></div>
            <div><span>请求发送</span><strong>{preflight.request_sent ? '异常：已发送' : '否'}</strong></div>
            <div><span>保存授权</span><strong>{preflight.key_persisted ? '异常' : '否'}</strong></div>
            <div><span>内网入口</span><strong>{preflight.private_host_allowlist_used ? '安全名单命中' : preflight.private_host_allowlist_configured ? '安全名单已配置' : '默认拦截'}</strong></div>
          </div>
          <div className="provider-preflight-paths">
            <span>将尝试的调用路径</span>
            {preflight.endpoint_paths.length
              ? preflight.endpoint_paths.map((path) => <strong key={path}>{path}</strong>)
              : <strong>{preflight.blocked_reason || '等待 API Base'}</strong>}
          </div>
          {preflight.warnings.length ? (
            <div className="provider-preflight-list">
              <span>提示</span>
              {preflight.warnings.map((item) => <p key={item}>{item}</p>)}
            </div>
          ) : null}
          <div className="provider-preflight-list next">
            <span>下一步</span>
            {preflight.next_actions.slice(0, 3).map((item) => <p key={item}>{item}</p>)}
          </div>
        </>
      ) : null}
    </div>
  )
}

function statusLabel(status?: string) {
  const labels: Record<string, string> = {
    ok: '可用',
    blocked: '已阻断',
    preview: '预览',
    checking: '检查中',
  }
  return labels[String(status || 'checking').toLowerCase()] || '待确认'
}
