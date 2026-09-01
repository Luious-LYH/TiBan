import { CheckCircle2, EyeOff, LoaderCircle, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { applyInstanceEmbedding, applyInstanceLLM, getInstanceSettings, restoreInstanceEmbedding, restoreInstanceLLM, testInstanceEmbedding, testInstanceLLM } from '../../api/client'
import { ErrorState, LoadingState } from '../../components/shared/AsyncState'

export function SettingsPage() {
  const settings = useQuery({ queryKey: ['instance-settings'], queryFn: getInstanceSettings })
  const client = useQueryClient()
  const [provider, setProvider] = useState('openai_compatible')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [batchSize, setBatchSize] = useState('32')
  const [notice, setNotice] = useState<string | null>(null)
  const refresh = () => void client.invalidateQueries({ queryKey: ['instance-settings'] })
  const llmTest = useMutation({ mutationFn: () => testInstanceLLM({ provider: baseUrl ? provider : undefined, base_url: baseUrl || undefined, model: model || undefined, api_key: apiKey || undefined }), onSuccess: (result) => setNotice(result.ok ? `智能模型连接成功${result.latency_ms ? ` · ${result.latency_ms} ms` : ''}` : (result.message ?? '连接失败')), onError: (error: Error) => setNotice(error.message) })
  const llmApply = useMutation({ mutationFn: () => applyInstanceLLM({ provider, base_url: baseUrl, model, api_key: apiKey || undefined }), onSuccess: () => { setApiKey(''); setNotice('已应用到当前运行实例；服务重启后恢复默认配置。'); refresh() }, onError: (error: Error) => setNotice(error.message) })
  const llmRestore = useMutation({ mutationFn: restoreInstanceLLM, onSuccess: () => { setNotice('已恢复服务默认配置。'); refresh() }, onError: (error: Error) => setNotice(error.message) })
  const embeddingTest = useMutation({ mutationFn: testInstanceEmbedding, onSuccess: (result) => setNotice(result.ok ? `Embedding 可用 · ${String(result.result?.model ?? '')}` : (result.message ?? 'Embedding 不可用')), onError: (error: Error) => setNotice(error.message) })
  const embeddingApply = useMutation({ mutationFn: () => applyInstanceEmbedding({ batch_size: Number(batchSize) }), onSuccess: () => { setNotice('已应用到后续检索与资料索引任务；服务重启后恢复默认值。'); refresh() }, onError: (error: Error) => setNotice(error.message) })
  const embeddingRestore = useMutation({ mutationFn: restoreInstanceEmbedding, onSuccess: () => { setNotice('Embedding 已恢复默认运行配置。'); refresh() }, onError: (error: Error) => setNotice(error.message) })

  if (settings.isPending) return <LoadingState label="正在读取当前实例配置…" />
  if (settings.isError) return <ErrorState message={settings.error.message} onRetry={() => void settings.refetch()} />
  const current = settings.data
  const busy = llmTest.isPending || llmApply.isPending || llmRestore.isPending || embeddingTest.isPending || embeddingApply.isPending || embeddingRestore.isPending

  return <div className="settings-page" data-testid="settings-page">
    <header className="settings-header"><div><h1>设置</h1><p>配置当前 TiBan 实例的智能能力。不会保存到账号；服务重启后恢复 .env 或 Docker 默认配置。</p></div><span>{current.llm.runtime_override || current.embedding.runtime_override ? '当前使用运行时配置' : '当前使用服务默认配置'}</span></header>
    {notice && <div className="settings-notice" role="status"><CheckCircle2 size={16} />{notice}</div>}
    <section className="settings-section"><header><div><h2>智能模型</h2><p>影响后续智能辅导与已启用的题目生成调用。已配置的连接地址和密钥不会回显。</p></div><span>{current.llm.api_key_configured ? '已配置' : '未配置'}</span></header><div className="settings-grid"><label>兼容模式<select value={provider} onChange={(event) => setProvider(event.target.value)}><option value="openai_compatible">OpenAI 兼容</option></select></label><label>模型名称<input value={model} onChange={(event) => setModel(event.target.value)} placeholder={current.llm.model || '例如 gpt-5.6-luna'} /></label><label className="settings-span-2">API Base URL<input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder={current.llm.base_url_configured ? '当前已配置，为安全起见不回显' : 'https://…/v1'} /></label><label className="settings-span-2">API Key <small>仅发送到当前后端进程，不写入浏览器存储。</small><div className="settings-secret"><input value={apiKey} onChange={(event) => setApiKey(event.target.value)} type="password" autoComplete="off" placeholder={current.llm.api_key_configured ? '保留现有密钥；填入可覆盖' : '输入当前实例的 API Key'} /><EyeOff size={16} /></div></label></div><div className="settings-actions"><button type="button" onClick={() => void llmTest.mutate()} disabled={busy || (!baseUrl && !current.llm.base_url_configured) || (!model && !current.llm.model)}>{baseUrl || model || apiKey ? '测试填写配置' : '测试当前连接'}</button><button className="settings-primary" type="button" onClick={() => void llmApply.mutate()} disabled={busy || !baseUrl || !model}>{llmApply.isPending ? <LoaderCircle className="s1-spin" size={15} /> : null}应用配置</button><button type="button" onClick={() => void llmRestore.mutate()} disabled={busy}><RotateCcw size={15} />恢复默认</button></div></section>
    <section className="settings-section"><header><div><h2>Embedding</h2><p>当前使用本地向量模型。为避免现有 Qdrant 索引维度不一致，本版不支持在线切换模型；只开放真实生效的批处理设置。</p></div><span>{current.embedding.mode === 'local' ? '本地运行' : current.embedding.mode}</span></header><div className="settings-grid"><label>当前模型<input value={current.embedding.model} readOnly /></label><label>批处理大小<input type="number" min="1" max="64" value={batchSize} onChange={(event) => setBatchSize(event.target.value)} /></label></div><div className="settings-actions"><button type="button" onClick={() => void embeddingTest.mutate()} disabled={busy}>测试 Embedding</button><button className="settings-primary" type="button" onClick={() => void embeddingApply.mutate()} disabled={busy}>应用配置</button><button type="button" onClick={() => void embeddingRestore.mutate()} disabled={busy}><RotateCcw size={15} />恢复默认</button></div></section>
  </div>
}
