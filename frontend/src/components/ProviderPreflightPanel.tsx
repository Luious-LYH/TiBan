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
          <span className="eyebrow">Base URL preflight</span>
          <strong>{loading ? '正在检查 API Base 安全策略' : ok ? 'API Base 可进入 Provider 调用流程' : 'API Base 暂不能进入 Provider 调用'}</strong>
          <p>预检只做 URL 规范化、安全策略和 endpoint 路径推导，不发送模型请求、不读取或保存 API key。</p>
        </div>
        <Tag tone={statusTone}>{preflight?.safety_status || 'checking'}</Tag>
      </div>
      {preflight ? (
        <>
          <div className="provider-preflight-grid">
            <div><span>模式</span><strong>{preflight.mode}</strong></div>
            <div><span>规范化预览</span><strong>{preflight.normalized_preview || '未配置'}</strong></div>
            <div><span>请求发送</span><strong>{preflight.request_sent ? '异常：已发送' : '否'}</strong></div>
            <div><span>保存 key</span><strong>{preflight.key_persisted ? '异常' : '否'}</strong></div>
          </div>
          <div className="provider-preflight-paths">
            <span>将尝试的 chat completions path</span>
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
