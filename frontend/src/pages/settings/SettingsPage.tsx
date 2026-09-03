import { CheckCircle2, Eye, EyeOff, LoaderCircle, RefreshCw, RotateCcw } from 'lucide-react'
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
  const [embeddingProvider, setEmbeddingProvider] = useState('siliconflow')
  const [embeddingBaseUrl, setEmbeddingBaseUrl] = useState('')
  const [embeddingModel, setEmbeddingModel] = useState('BAAI/bge-m3')
  const [localModel, setLocalModel] = useState('BAAI/bge-small-zh-v1.5')
  const [embeddingKey, setEmbeddingKey] = useState('')
  const [embeddingConfigMode, setEmbeddingConfigMode] = useState<'default' | 'custom'>('default')
  const [showApiKey, setShowApiKey] = useState(false)
  const [showEmbeddingKey, setShowEmbeddingKey] = useState(false)
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
    setEmbeddingProvider(current.embedding.provider)
    setEmbeddingModel(current.embedding.model)
    setLocalModel(current.embedding.local_model)
    setEmbeddingConfigMode(current.embedding.runtime_override ? 'custom' : 'default')
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
  const embeddingTest = useMutation({ mutationFn: () => embeddingConfigMode === 'default' ? testInstanceEmbedding({}) : testInstanceEmbedding({ mode: 'api', provider: embeddingProvider, base_url: embeddingBaseUrl || undefined, api_key: embeddingKey || undefined, model: embeddingModel }), onSuccess: (result) => setNotice(result.ok ? `Embedding 连接成功 · ${String(result.result?.model ?? embeddingModel)}` : (result.message ?? 'Embedding 不可用')), onError: (error: Error) => setNotice(error.message) })
  const embeddingApply = useMutation({ mutationFn: () => embeddingConfigMode === 'default' ? restoreInstanceEmbedding() : applyInstanceEmbedding({ batch_size: Number(batchSize), mode: 'api', provider: embeddingProvider, base_url: embeddingBaseUrl, api_key: embeddingKey || undefined, model: embeddingModel, local_model: localModel, reranker_mode: rerankerMode, reranker_provider: rerankerProvider, reranker_base_url: embeddingBaseUrl, reranker_model: rerankerModel }), onSuccess: () => { setEmbeddingKey(''); setNotice(embeddingConfigMode === 'default' ? '已切换为项目默认 Embedding 配置。' : '自定义 Embedding 配置已应用；知识库和长期记忆索引需要重建。'); refresh() }, onError: (error: Error) => setNotice(error.message) })
  const embeddingRestore = useMutation({ mutationFn: restoreInstanceEmbedding, onSuccess: () => { setEmbeddingConfigMode('default'); setEmbeddingKey(''); setNotice('Embedding 已恢复项目默认配置；索引需要按当前默认模型重建。'); refresh() }, onError: (error: Error) => setNotice(error.message) })
  const rebuild = useMutation({ mutationFn: rebuildInstanceIndexes, onSuccess: (result) => { setNotice(`已创建索引重建任务：${result.stage}。`); setWatchingRebuild(true); refresh() }, onError: (error: Error) => setNotice(error.message) })

  if (settings.isPending) return <LoadingState label="正在读取当前实例配置…" />
  if (settings.isError) return <ErrorState message={settings.error.message} onRetry={() => void settings.refetch()} />
  const current = settings.data
  const busy = llmTest.isPending || llmApply.isPending || llmRestore.isPending || embeddingTest.isPending || embeddingApply.isPending || embeddingRestore.isPending || rebuild.isPending
  const indexReady = current.embedding.knowledge_index_status === 'ready' && current.embedding.memory_index_status === 'ready'

  return <div className="settings-page" data-testid="settings-page">
    <header className="settings-header"><div><h1>设置</h1><p>配置当前 TiBan 实例的智能能力。不会保存到账号；服务重启后恢复 .env 或 Docker 默认配置。</p></div><span>{current.llm.runtime_override || current.embedding.runtime_override ? '当前使用运行时配置' : '当前使用服务默认配置'}</span></header>
    {notice && <div className="settings-notice" role="status"><CheckCircle2 size={16} />{notice}</div>}
    <section className="settings-section"><header><div><h2>智能模型</h2><p>影响智能辅导、带教 Agent 与已启用的题目生成。地址和密钥不会回显或写入浏览器存储。</p></div><span>{current.llm.api_key_configured ? '已配置' : '未配置'}</span></header><div className="settings-grid"><label>兼容模式<select value={provider} onChange={(event) => setProvider(event.target.value)}><option value="openai_compatible">OpenAI 兼容</option></select></label><label>模型名称<input value={model} onChange={(event) => setModel(event.target.value)} /></label><label className="settings-span-2">API Base URL<input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder={current.llm.base_url_configured ? '当前已配置，为安全起见不回显' : 'https://…/v1'} /></label><label className="settings-span-2">API Key <small>仅发送到当前后端进程。</small><div className="settings-secret"><input value={apiKey} onChange={(event) => setApiKey(event.target.value)} type={showApiKey ? 'text' : 'password'} autoComplete="off" placeholder={current.llm.api_key_configured ? '保留现有密钥；填入可覆盖' : '输入当前实例的 API Key'} /><button type="button" aria-label={showApiKey ? '隐藏 API Key' : '显示 API Key'} onClick={() => setShowApiKey((value) => !value)}>{showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}</button></div></label></div><div className="settings-actions"><button type="button" onClick={() => void llmTest.mutate()} disabled={busy || (!baseUrl && !current.llm.base_url_configured)}>{baseUrl || model || apiKey ? '测试填写配置' : '测试当前连接'}</button><button className="settings-primary" type="button" onClick={() => void llmApply.mutate()} disabled={busy || !baseUrl || !model}>{llmApply.isPending && <LoaderCircle className="s1-spin" size={15} />}应用配置</button><button type="button" onClick={() => void llmRestore.mutate()} disabled={busy}><RotateCcw size={15} />恢复默认</button></div></section>
    <section className="settings-section settings-embedding-section"><header><div><h2>Embedding 模型</h2><p>用于题库、知识库和学习记忆的语义索引。通常使用项目默认配置即可。</p></div><span>{indexReady ? '索引就绪' : '索引待处理'}</span></header><div className="settings-choice"><span>配置方式</span><div role="group" aria-label="Embedding 配置方式"><button type="button" className={embeddingConfigMode === 'default' ? 'is-active' : ''} onClick={() => setEmbeddingConfigMode('default')}>项目默认</button><button type="button" className={embeddingConfigMode === 'custom' ? 'is-active' : ''} onClick={() => setEmbeddingConfigMode('custom')}>自定义 API</button></div></div>{embeddingConfigMode === 'default' ? <div className="settings-default-card"><strong>项目默认配置</strong><p>跟随部署环境的统一配置：<b>SiliconFlow · BAAI/bge-m3</b>。无需填写地址和密钥。</p></div> : <div className="settings-grid"><label className="settings-span-2">API Base URL<input value={embeddingBaseUrl} onChange={(event) => setEmbeddingBaseUrl(event.target.value)} placeholder="https://api.siliconflow.cn/v1" /></label><label className="settings-span-2">API Key <small>仅发送到当前后端进程，不会回显或写入浏览器存储。</small><div className="settings-secret"><input type={showEmbeddingKey ? 'text' : 'password'} autoComplete="off" value={embeddingKey} onChange={(event) => setEmbeddingKey(event.target.value)} placeholder="输入自定义 Embedding API Key" /><button type="button" aria-label={showEmbeddingKey ? '隐藏 Embedding API Key' : '显示 Embedding API Key'} onClick={() => setShowEmbeddingKey((value) => !value)}>{showEmbeddingKey ? <EyeOff size={16} /> : <Eye size={16} />}</button></div></label><label className="settings-span-2">Embedding 模型<input value={embeddingModel} onChange={(event) => setEmbeddingModel(event.target.value)} placeholder="BAAI/bge-m3" /></label></div>}<p className="settings-warning">更换模型或连接方式会让两个派生索引等待重建；原始资料、作答记录、FSRS 和 Learning Memory 不会被删除。</p><div className="settings-index-status"><span>知识索引：{statusLabel(current.embedding.knowledge_index_status)}</span><span>学习记忆索引：{statusLabel(current.embedding.memory_index_status)}</span></div><div className="settings-actions"><button type="button" onClick={() => void embeddingTest.mutate()} disabled={busy}>{embeddingConfigMode === 'custom' ? '测试自定义 API' : '测试项目默认'}</button><button className="settings-primary" type="button" onClick={() => void embeddingApply.mutate()} disabled={busy || (embeddingConfigMode === 'custom' && !embeddingModel)}>{embeddingApply.isPending && <LoaderCircle className="s1-spin" size={15} />}{embeddingConfigMode === 'default' ? '使用项目默认' : '应用配置'}</button><button type="button" onClick={() => void rebuild.mutate()} disabled={busy || indexReady}>{rebuild.isPending && <LoaderCircle className="s1-spin" size={15} />}<RefreshCw size={15} />重建索引</button><button type="button" onClick={() => void embeddingRestore.mutate()} disabled={busy}><RotateCcw size={15} />恢复默认</button></div></section>
  </div>
}

function statusLabel(value: string) { return ({ ready: '就绪', stale: '待重建', rebuilding: '重建中', failed: '失败' } as Record<string, string>)[value] ?? value }
