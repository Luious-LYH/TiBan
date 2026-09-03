import { CheckCircle2, EyeOff, LoaderCircle, RefreshCw, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { applyInstanceEmbedding, applyInstanceLLM, getInstanceSettings, rebuildInstanceIndexes, restoreInstanceEmbedding, restoreInstanceLLM, testInstanceEmbedding, testInstanceLLM } from '../../api/client'
import { ErrorState, LoadingState } from '../../components/shared/AsyncState'

type EmbeddingMode = 'api' | 'local'

export function SettingsPage() {
  const settings = useQuery({ queryKey: ['instance-settings'], queryFn: getInstanceSettings })
  const client = useQueryClient()
  const hydrated = useRef(false)
  const [provider, setProvider] = useState('openai_compatible')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [embeddingMode, setEmbeddingMode] = useState<EmbeddingMode>('api')
  const [embeddingProvider, setEmbeddingProvider] = useState('siliconflow')
  const [embeddingBaseUrl, setEmbeddingBaseUrl] = useState('')
  const [embeddingModel, setEmbeddingModel] = useState('BAAI/bge-m3')
  const [localModel, setLocalModel] = useState('BAAI/bge-small-zh-v1.5')
  const [embeddingKey, setEmbeddingKey] = useState('')
  const [rerankerMode, setRerankerMode] = useState<EmbeddingMode>('api')
  const [rerankerProvider, setRerankerProvider] = useState('siliconflow')
  const [rerankerModel, setRerankerModel] = useState('BAAI/bge-reranker-v2-m3')
  const [batchSize, setBatchSize] = useState('32')
  const [notice, setNotice] = useState<string | null>(null)
  const [watchingRebuild, setWatchingRebuild] = useState(false)
  const refresh = () => void client.invalidateQueries({ queryKey: ['instance-settings'] })

  useEffect(() => {
    if (!settings.data || hydrated.current) return
    hydrated.current = true
    const current = settings.data
    setProvider(current.llm.provider)
    setModel(current.llm.model)
    setEmbeddingMode(current.embedding.mode === 'local' ? 'local' : 'api')
    setEmbeddingProvider(current.embedding.provider)
    setEmbeddingModel(current.embedding.model)
    setLocalModel(current.embedding.local_model)
    setRerankerMode(current.embedding.reranker_mode === 'local' ? 'local' : 'api')
    setRerankerProvider(current.embedding.reranker_provider)
    setRerankerModel(current.embedding.reranker_model)
    setBatchSize(String(current.embedding.batch_size))
  }, [settings.data])

  useEffect(() => {
    if (!watchingRebuild) return
    const timer = window.setInterval(() => {
      void settings.refetch().then((result) => {
        const status = result.data?.embedding
        if (!status || ['ready', 'failed'].includes(status.knowledge_index_status) && ['ready', 'failed'].includes(status.memory_index_status)) setWatchingRebuild(false)
      })
    }, 2_000)
    return () => window.clearInterval(timer)
  }, [settings, watchingRebuild])

  const llmTest = useMutation({ mutationFn: () => testInstanceLLM({ provider: baseUrl ? provider : undefined, base_url: baseUrl || undefined, model: model || undefined, api_key: apiKey || undefined }), onSuccess: (result) => setNotice(result.ok ? `智能模型连接成功${result.latency_ms ? ` · ${result.latency_ms} ms` : ''}` : (result.message ?? '连接失败')), onError: (error: Error) => setNotice(error.message) })
  const llmApply = useMutation({ mutationFn: () => applyInstanceLLM({ provider, base_url: baseUrl, model, api_key: apiKey || undefined }), onSuccess: () => { setApiKey(''); setNotice('已应用到当前运行实例；服务重启后恢复默认配置。'); refresh() }, onError: (error: Error) => setNotice(error.message) })
  const llmRestore = useMutation({ mutationFn: restoreInstanceLLM, onSuccess: () => { setNotice('已恢复服务默认配置。'); refresh() }, onError: (error: Error) => setNotice(error.message) })
  const embeddingTest = useMutation({ mutationFn: () => testInstanceEmbedding({ mode: embeddingMode, provider: embeddingProvider, base_url: embeddingBaseUrl || undefined, api_key: embeddingKey || undefined, model: embeddingModel, local_model: localModel }), onSuccess: (result) => setNotice(result.ok ? `Embedding 连接成功 · ${String(result.result?.model ?? embeddingModel)}` : (result.message ?? 'Embedding 不可用')), onError: (error: Error) => setNotice(error.message) })
  const embeddingApply = useMutation({ mutationFn: () => applyInstanceEmbedding({ batch_size: Number(batchSize), mode: embeddingMode, provider: embeddingProvider, base_url: embeddingBaseUrl, api_key: embeddingKey || undefined, model: embeddingModel, local_model: localModel, reranker_mode: rerankerMode, reranker_provider: rerankerProvider, reranker_base_url: embeddingBaseUrl, reranker_model: rerankerModel }), onSuccess: () => { setEmbeddingKey(''); setNotice('配置已应用；知识库和长期记忆索引已标记为需要重建。'); refresh() }, onError: (error: Error) => setNotice(error.message) })
  const embeddingRestore = useMutation({ mutationFn: restoreInstanceEmbedding, onSuccess: () => { setNotice('Embedding 已恢复默认运行配置；索引需要按当前默认模型重建。'); refresh() }, onError: (error: Error) => setNotice(error.message) })
  const rebuild = useMutation({ mutationFn: rebuildInstanceIndexes, onSuccess: (result) => { setNotice(`已创建索引重建任务：${result.stage}。`); setWatchingRebuild(true); refresh() }, onError: (error: Error) => setNotice(error.message) })

  if (settings.isPending) return <LoadingState label="正在读取当前实例配置…" />
  if (settings.isError) return <ErrorState message={settings.error.message} onRetry={() => void settings.refetch()} />
  const current = settings.data
  const busy = llmTest.isPending || llmApply.isPending || llmRestore.isPending || embeddingTest.isPending || embeddingApply.isPending || embeddingRestore.isPending || rebuild.isPending
  const indexReady = current.embedding.knowledge_index_status === 'ready' && current.embedding.memory_index_status === 'ready'

  return <div className="settings-page" data-testid="settings-page">
    <header className="settings-header"><div><h1>设置</h1><p>配置当前 TiBan 实例的智能能力。不会保存到账号；服务重启后恢复 .env 或 Docker 默认配置。</p></div><span>{current.llm.runtime_override || current.embedding.runtime_override ? '当前使用运行时配置' : '当前使用服务默认配置'}</span></header>
    {notice && <div className="settings-notice" role="status"><CheckCircle2 size={16} />{notice}</div>}
    <section className="settings-section"><header><div><h2>智能模型</h2><p>影响智能辅导、带教 Agent 与已启用的题目生成。地址和密钥不会回显或写入浏览器存储。</p></div><span>{current.llm.api_key_configured ? '已配置' : '未配置'}</span></header><div className="settings-grid"><label>兼容模式<select value={provider} onChange={(event) => setProvider(event.target.value)}><option value="openai_compatible">OpenAI 兼容</option></select></label><label>模型名称<input value={model} onChange={(event) => setModel(event.target.value)} /></label><label className="settings-span-2">API Base URL<input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder={current.llm.base_url_configured ? '当前已配置，为安全起见不回显' : 'https://…/v1'} /></label><label className="settings-span-2">API Key <small>仅发送到当前后端进程。</small><div className="settings-secret"><input value={apiKey} onChange={(event) => setApiKey(event.target.value)} type="password" autoComplete="off" placeholder={current.llm.api_key_configured ? '保留现有密钥；填入可覆盖' : '输入当前实例的 API Key'} /><EyeOff size={16} /></div></label></div><div className="settings-actions"><button type="button" onClick={() => void llmTest.mutate()} disabled={busy || (!baseUrl && !current.llm.base_url_configured)}>{baseUrl || model || apiKey ? '测试填写配置' : '测试当前连接'}</button><button className="settings-primary" type="button" onClick={() => void llmApply.mutate()} disabled={busy || !baseUrl || !model}>{llmApply.isPending && <LoaderCircle className="s1-spin" size={15} />}应用配置</button><button type="button" onClick={() => void llmRestore.mutate()} disabled={busy}><RotateCcw size={15} />恢复默认</button></div></section>
    <section className="settings-section"><header><div><h2>Embedding</h2><p>在线实例默认使用 SiliconFlow / BAAI/bge-m3；知识资料与长期学习记忆使用彼此独立的语义索引。</p></div><span>{indexReady ? '索引就绪' : '索引待处理'}</span></header><p className="settings-warning">更换 Embedding 模型会使当前向量索引失效，需要重新构建知识库与长期记忆语义索引。原始资料、作答记录、FSRS 和 Learning Memory 原文不会被删除。</p><div className="settings-grid"><label>模式<select value={embeddingMode} onChange={(event) => setEmbeddingMode(event.target.value as EmbeddingMode)}><option value="api">API</option><option value="local">Local</option></select></label><label>Provider<input value={embeddingProvider} onChange={(event) => setEmbeddingProvider(event.target.value)} disabled={embeddingMode === 'local'} /></label>{embeddingMode === 'api' ? <><label className="settings-span-2">API Base URL<input value={embeddingBaseUrl} onChange={(event) => setEmbeddingBaseUrl(event.target.value)} placeholder={current.embedding.base_url_configured ? '当前已配置，为安全起见不回显' : 'https://api.siliconflow.cn/v1'} /></label><label className="settings-span-2">API Key <small>仅发送至当前实例。</small><div className="settings-secret"><input type="password" autoComplete="off" value={embeddingKey} onChange={(event) => setEmbeddingKey(event.target.value)} placeholder={current.embedding.api_key_configured ? '保留现有密钥；填入可覆盖' : '输入 Embedding API Key'} /><EyeOff size={16} /></div></label><label>Embedding 模型<input value={embeddingModel} onChange={(event) => setEmbeddingModel(event.target.value)} /></label></> : <label className="settings-span-2">本地模型 ID / 路径<input value={localModel} onChange={(event) => setLocalModel(event.target.value)} /></label>}<label>Reranker 模式<select value={rerankerMode} onChange={(event) => setRerankerMode(event.target.value as EmbeddingMode)}><option value="api">API</option><option value="local">Local</option></select></label><label>Reranker Provider<input value={rerankerProvider} onChange={(event) => setRerankerProvider(event.target.value)} disabled={rerankerMode === 'local'} /></label><label className="settings-span-2">Reranker 模型<input value={rerankerModel} onChange={(event) => setRerankerModel(event.target.value)} /></label><label>批处理大小<input type="number" min="1" max="64" value={batchSize} onChange={(event) => setBatchSize(event.target.value)} /></label></div><div className="settings-index-status"><span>知识索引：{statusLabel(current.embedding.knowledge_index_status)}</span><span>学习记忆索引：{statusLabel(current.embedding.memory_index_status)}</span></div><div className="settings-actions"><button type="button" onClick={() => void embeddingTest.mutate()} disabled={busy}>测试连接</button><button className="settings-primary" type="button" onClick={() => void embeddingApply.mutate()} disabled={busy || !embeddingModel}>{embeddingApply.isPending && <LoaderCircle className="s1-spin" size={15} />}应用配置</button><button type="button" onClick={() => void rebuild.mutate()} disabled={busy || indexReady}>{rebuild.isPending && <LoaderCircle className="s1-spin" size={15} />}<RefreshCw size={15} />重建两个索引</button><button type="button" onClick={() => void embeddingRestore.mutate()} disabled={busy}><RotateCcw size={15} />恢复默认</button></div></section>
  </div>
}

function statusLabel(value: string) { return ({ ready: '就绪', stale: '待重建', rebuilding: '重建中', failed: '失败' } as Record<string, string>)[value] ?? value }
