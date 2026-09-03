import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, LoaderCircle, Play, Plus, RefreshCw, Save, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { createEvaluationSuite, createRagEvaluation, deleteEvaluationExperiments, deleteSavedRagProfile, getEvaluationExperiment, getLatestEvaluationExperiment, getLatestEvaluationSuite, getSavedRagProfiles, saveRagProfile, type EvalSuite, type EvaluationCatalog, type EvaluationExperiment, type RetrievalProfile, type SavedRagProfile } from '../../api/client'
import { EvaluationConfirmDialog } from './EvaluationConfirmDialog'
import { displayModelName } from './evaluationDisplay'

const percent = (value: unknown) => typeof value === 'number' ? `${Math.round(value * 100)}%` : '—'
const latency = (value: unknown) => typeof value === 'number' ? `${value}ms` : '—'
const metric = (value: unknown) => typeof value === 'number' ? String(value) : '—'
const errorMessage = (error: unknown) => error instanceof Error ? error.message : '操作失败，请检查评测集和检索配置。'
const freshVariant = (index: number): RetrievalProfile => ({ name: `对比方案 ${index + 1}`, mode: 'hybrid', top_k: 5, candidate_pool: 20, rerank_enabled: false, rrf_k: 60, section_dedupe: true })
type EditableProfile = RetrievalProfile & Partial<Pick<SavedRagProfile, 'profile_id' | 'bank_id' | 'created_at' | 'updated_at'>> & { persisted?: RetrievalProfile }

function toRetrievalProfile(profile: EditableProfile): RetrievalProfile {
  return { name: profile.name, mode: profile.mode, top_k: profile.top_k, candidate_pool: profile.candidate_pool, rerank_enabled: profile.rerank_enabled, rrf_k: profile.rrf_k, section_dedupe: profile.section_dedupe }
}

function profileIsDirty(profile: EditableProfile): boolean {
  return !profile.persisted || JSON.stringify(toRetrievalProfile(profile)) !== JSON.stringify(profile.persisted)
}

function editableFromSaved(profile: SavedRagProfile): EditableProfile {
  const values = { name: profile.name, mode: profile.mode, top_k: profile.top_k, candidate_pool: profile.candidate_pool, rerank_enabled: profile.rerank_enabled, rrf_k: profile.rrf_k, section_dedupe: profile.section_dedupe }
  return { ...profile, persisted: values }
}

export function RagEvaluationTab({ catalog }: { catalog: EvaluationCatalog }) {
  const queryClient = useQueryClient()
  const [bankId, setBankId] = useState(catalog.banks[0]?.bank_id ?? '')
  const [sampleSize, setSampleSize] = useState(10)
  const [suite, setSuite] = useState<EvalSuite | null>(null)
  const [variantDrafts, setVariantDrafts] = useState<Record<string, EditableProfile[]>>({})
  const [experiment, setExperiment] = useState<EvaluationExperiment | null>(null)
  const [confirmResample, setConfirmResample] = useState(false)
  const latestSuite = useQuery({ queryKey: ['evaluation-latest-suite', bankId], queryFn: () => getLatestEvaluationSuite(bankId), enabled: Boolean(bankId), retry: false })
  const latestExperiment = useQuery({ queryKey: ['evaluation-latest-experiment', bankId, 'rag'], queryFn: () => getLatestEvaluationExperiment(bankId, 'rag'), enabled: Boolean(bankId), retry: false, staleTime: 0 })
  const savedProfiles = useQuery({ queryKey: ['evaluation-rag-profiles', bankId], queryFn: () => getSavedRagProfiles(bankId), enabled: Boolean(bankId), retry: false })
  const [savingIndex, setSavingIndex] = useState<number | null>(null)
  const [deletingIndex, setDeletingIndex] = useState<number | null>(null)
  const persistedExperiment = experiment ?? latestExperiment.data ?? null
  const activeSuite = suite ?? persistedExperiment?.suite ?? latestSuite.data ?? null
  const variants = variantDrafts[bankId] ?? savedProfiles.data?.map(editableFromSaved) ?? []
  const setVariants = (updater: (items: EditableProfile[]) => EditableProfile[]) => setVariantDrafts((drafts) => ({
    ...drafts,
    [bankId]: updater(drafts[bankId] ?? savedProfiles.data?.map(editableFromSaved) ?? []),
  }))
  const createSuite = useMutation({ mutationFn: () => createEvaluationSuite({ bank_id: bankId, sample_size: sampleSize }), onSuccess: setSuite })
  const resample = useMutation({
    mutationFn: async () => {
      await deleteEvaluationExperiments(bankId, 'rag')
      setExperiment(null)
      queryClient.setQueryData(['evaluation-latest-experiment', bankId, 'rag'], null)
      return createEvaluationSuite({ bank_id: bankId, sample_size: sampleSize })
    },
    onSuccess: (result) => {
      setSuite(result)
      setConfirmResample(false)
      queryClient.setQueryData(['evaluation-latest-suite', bankId], result)
    },
  })
  const createExperiment = useMutation({
    mutationFn: () => createRagEvaluation({ suite_id: activeSuite?.suite_id ?? '', model: catalog.runtime_models[0], variants: variants.map(toRetrievalProfile) }),
    onSuccess: (result) => {
      setExperiment(result)
      queryClient.setQueryData(['evaluation-latest-experiment', bankId, 'rag'], result)
    },
  })
  const saveProfileMutation = useMutation({
    mutationFn: ({ profile }: { index: number; profile: EditableProfile }) => saveRagProfile(bankId, toRetrievalProfile(profile), profile.profile_id),
    onMutate: ({ index }) => setSavingIndex(index),
    onSuccess: (saved, { index }) => {
      setVariants((items) => items.map((item, currentIndex) => currentIndex === index ? editableFromSaved(saved) : item))
      queryClient.setQueryData<SavedRagProfile[]>(['evaluation-rag-profiles', bankId], (items) => items ? items.some((item) => item.profile_id === saved.profile_id) ? items.map((item) => item.profile_id === saved.profile_id ? saved : item) : [...items, saved] : [saved])
    },
    onSettled: () => setSavingIndex(null),
  })
  const deleteProfileMutation = useMutation({
    mutationFn: ({ profileId }: { index: number; profileId: string }) => deleteSavedRagProfile(bankId, profileId),
    onMutate: ({ index }) => setDeletingIndex(index),
    onSuccess: (_result, { index, profileId }) => {
      setVariants((items) => items.filter((_item, currentIndex) => currentIndex !== index))
      queryClient.setQueryData<SavedRagProfile[]>(['evaluation-rag-profiles', bankId], (items) => items?.filter((item) => item.profile_id !== profileId) ?? [])
    },
    onSettled: () => setDeletingIndex(null),
  })
  const polling = useQuery({ queryKey: ['rag-evaluation-experiment', persistedExperiment?.experiment_id], queryFn: () => getEvaluationExperiment(persistedExperiment!.experiment_id), enabled: Boolean(persistedExperiment && persistedExperiment.status !== 'completed' && persistedExperiment.status !== 'partial_failed'), retry: false, refetchInterval: (query) => query.state.data?.status === 'completed' || query.state.data?.status === 'partial_failed' ? false : 1200 })
  const current = polling.data ?? persistedExperiment
  const update = (index: number, patch: Partial<RetrievalProfile>) => setVariants((items) => items.map((item, currentIndex) => currentIndex === index ? { ...item, ...patch } : item))
  const remove = (index: number) => {
    const profile = variants[index]
    if (!profile) return
    if (profile.profile_id) {
      deleteProfileMutation.mutate({ index, profileId: profile.profile_id })
    } else {
      setVariants((items) => items.filter((_item, currentIndex) => currentIndex !== index))
    }
  }
  const requestSuite = () => activeSuite ? setConfirmResample(true) : createSuite.mutate()
  const activeRun = Boolean(current && (current.status === 'running' || current.status === 'queued'))
  const canRun = Boolean(activeSuite && !createExperiment.isPending && !activeRun)
  return <section className="evaluation-lab" data-testid="rag-evaluation-tab">
    <div className="evaluation-panel evaluation-setup evaluation-rag-setup">
      <header className="evaluation-config-heading"><div><span>RAG 评测配置</span><h2>固定知识条件，只比较检索策略</h2><p>题目、知识快照、Embedding/index 版本、回答模型和 Prompt 在实验开始时冻结。</p></div><span className="evaluation-status-badge"><RefreshCw size={14} />可复现实验</span></header>
      <div className="evaluation-config-grid">
        <div className="evaluation-field"><span>01 · 选择题库</span><select aria-label="RAG 评测题库" value={bankId} onChange={(event) => { setBankId(event.target.value); setSuite(null); setExperiment(null) }}>{catalog.banks.map((bank) => <option value={bank.bank_id} key={bank.bank_id}>{bank.name}</option>)}</select><small>可评测题目 {catalog.banks.find((bank) => bank.bank_id === bankId)?.eligible_question_count ?? 0} 道</small></div>
        <div className="evaluation-field evaluation-set-field"><span>02 · 评测集</span><div className="evaluation-suite-line">{activeSuite ? <div className="evaluation-set-chip"><strong>本次评测：{activeSuite.sample_size} 道题</strong><small>评测集编号 {activeSuite.suite_short}</small></div> : <div className="evaluation-set-placeholder">{latestSuite.isPending ? '正在读取已保存的评测集…' : latestSuite.isError ? '已保存评测集暂时不可用' : '尚未创建评测集'}</div>}<input aria-label="评测题量" type="number" min="1" max="100" value={sampleSize} onChange={(event) => setSampleSize(Math.max(1, Math.min(100, Number(event.target.value) || 1)))} /><button type="button" onClick={requestSuite} disabled={createSuite.isPending || resample.isPending || !bankId}><RefreshCw size={14} className={createSuite.isPending || resample.isPending ? 's1-spin' : ''} />{activeSuite ? '重新抽样' : '创建评测集'}</button></div><small>当前评测集会保留，点击“重新抽样”后才会更换题目。</small></div>
      </div>
      <div className="evaluation-fixed-conditions"><span>03 · 固定运行条件</span><div className="evaluation-condition-chips"><span>回答模型 <strong>{displayModelName(catalog.runtime_models[0] || '未配置')}</strong></span><span>Prompt <strong>{catalog.prompt_version}</strong></span><span>temperature <strong>0</strong></span><span>fallback <strong>关闭</strong></span></div></div>
      <div className="evaluation-baseline"><div><span>项目默认方案</span><strong>{catalog.default_profile.name}</strong></div><small>{describe(catalog.default_profile)}</small><em>每次评测都会保留作对照</em></div>
      <div className="evaluation-variants"><header><div><span>04 · 对比方案</span><p>保存后可在这个题库的后续评测中继续使用。最多保存两个方案。</p></div><button type="button" disabled={variants.length >= 2 || savedProfiles.isPending} onClick={() => setVariants((items) => [...items, freshVariant(items.length)])}><Plus size={14} />添加方案</button></header>{savedProfiles.isPending && variants.length === 0 && <div className="evaluation-variant-empty evaluation-variant-loading"><LoaderCircle size={14} className="s1-spin" />正在读取已保存方案…</div>}{!savedProfiles.isPending && variants.length === 0 && <div className="evaluation-variant-empty">还没有保存的对比方案。需要时添加一个方案，保存后即可再次使用。</div>}{variants.map((profile, index) => <ProfileEditor key={profile.profile_id ?? `draft-${index}`} profile={profile} saving={savingIndex === index} deleting={deletingIndex === index} onChange={(patch) => update(index, patch)} onSave={() => saveProfileMutation.mutate({ index, profile })} onRemove={() => remove(index)} />)}</div>
      {latestSuite.isError && <p className="evaluation-error" role="alert">{errorMessage(latestSuite.error)} 可直接创建新的评测集。</p>}
      {createSuite.error && <p className="evaluation-error" role="alert">{errorMessage(createSuite.error)}</p>}
      {latestExperiment.isError && <p className="evaluation-error" role="alert">已保存的 RAG 评测结果暂时无法读取。</p>}
      {resample.error && <p className="evaluation-error" role="alert">{errorMessage(resample.error)}</p>}
      {createExperiment.error && <p className="evaluation-error" role="alert">{errorMessage(createExperiment.error)}</p>}
      {savedProfiles.isError && <p className="evaluation-error" role="alert">已保存的对比方案暂时无法读取。</p>}
      {(saveProfileMutation.error || deleteProfileMutation.error) && <p className="evaluation-error" role="alert">{errorMessage(saveProfileMutation.error ?? deleteProfileMutation.error)}</p>}
      <div className="evaluation-action-row"><small>Recall@K 仅在题库存在真实 Gold Evidence 标注时计算，否则显示 —。</small><button className="evaluation-primary evaluation-rag-primary" type="button" disabled={!canRun} onClick={() => createExperiment.mutate()}><Play size={15} />开始 RAG 评测</button></div>
    </div>
    {current && current.status !== 'completed' && current.status !== 'partial_failed' && <div className="evaluation-progress" role="status"><LoaderCircle size={16} className="s1-spin" /><span>{current.runs[0]?.stage ?? '正在创建后台任务…'} · {current.runs[0]?.progress ?? 0}%</span></div>}
    <RagLeaderboard experiment={current} />
    <EvaluationConfirmDialog open={confirmResample} bankName={catalog.banks.find((bank) => bank.bank_id === bankId)?.name ?? bankId} evaluationType="rag" pending={resample.isPending} error={resample.error ? errorMessage(resample.error) : null} onCancel={() => { if (!resample.isPending) { setConfirmResample(false); resample.reset() } }} onConfirm={() => resample.mutate()} />
  </section>
}

function ProfileEditor({ profile, saving, deleting, onChange, onSave, onRemove }: { profile: EditableProfile; saving: boolean; deleting: boolean; onChange: (patch: Partial<RetrievalProfile>) => void; onSave: () => void; onRemove: () => void }) {
  const dirty = profileIsDirty(profile)
  return <article className="evaluation-profile"><div className="evaluation-profile-head"><input aria-label="方案名称" value={profile.name} onChange={(event) => onChange({ name: event.target.value })} /><div className="evaluation-profile-actions"><span className={dirty ? 'evaluation-profile-status is-dirty' : 'evaluation-profile-status'}>{dirty ? '未保存修改' : <><Check size={12} />已保存</>}</span><button type="button" aria-label="删除方案" title="删除方案" disabled={saving || deleting} onClick={onRemove}><Trash2 size={14} /></button><button type="button" aria-label="保存方案" title={dirty ? '保存方案' : '方案已保存'} disabled={!dirty || saving || deleting} onClick={onSave}>{saving ? <LoaderCircle size={14} className="s1-spin" /> : <Save size={14} />}</button></div></div><div className="evaluation-profile-grid"><label>Retrieval Mode<select aria-label="Retrieval Mode" value={profile.mode} onChange={(event) => onChange({ mode: event.target.value as RetrievalProfile['mode'] })}><option value="sparse">Sparse</option><option value="dense">Dense</option><option value="hybrid">Hybrid</option></select></label><label>Top-K<input aria-label="Top-K" type="number" min="1" max="12" value={profile.top_k} onChange={(event) => onChange({ top_k: Number(event.target.value) })} /></label>{profile.mode !== 'sparse' && <><label>Candidate Pool<input aria-label="Candidate Pool" type="number" min="1" max="80" value={profile.candidate_pool} onChange={(event) => onChange({ candidate_pool: Number(event.target.value) })} /></label><label className="evaluation-check"><input aria-label="Reranker" type="checkbox" checked={profile.rerank_enabled} onChange={(event) => onChange({ rerank_enabled: event.target.checked })} />Reranker</label></>}{profile.mode === 'hybrid' && <label>RRF K<input aria-label="RRF K" type="number" min="1" max="240" value={profile.rrf_k} onChange={(event) => onChange({ rrf_k: Number(event.target.value) })} /></label>}<label className="evaluation-check"><input aria-label="Section Dedupe" type="checkbox" checked={profile.section_dedupe} onChange={(event) => onChange({ section_dedupe: event.target.checked })} />Section Dedupe</label></div></article>
}

function RagLeaderboard({ experiment }: { experiment: EvaluationExperiment | null }) {
  if (!experiment) return <div className="evaluation-empty"><strong>等待开始 RAG 评测</strong><span>没有真实 Gold Evidence/chunk 标注时，Recall@K 会如实显示为 —。</span></div>
  return <section className="evaluation-panel evaluation-results-panel"><header className="evaluation-result-heading"><div><span>RAG 评测结果</span><h2>冻结知识快照 · 评测集编号 {experiment.suite.suite_short}</h2></div><small>{experiment.status === 'completed' ? '评测完成' : experiment.status === 'partial_failed' ? '部分方案失败' : '运行中'}</small></header><div className="evaluation-table-wrap"><table className="evaluation-table"><thead><tr><th>方案</th><th>Answer Accuracy</th><th>P50 延迟</th><th>Avg Context Tokens</th><th>Recall@K</th></tr></thead><tbody>{experiment.runs.map((run) => <tr key={run.run_id}><td><strong>{run.retrieval_profile ? run.name : '项目默认方案'}</strong><small>{run.status === 'completed' ? '已完成' : `${run.stage} · ${run.progress}%`}</small></td><td>{percent(run.aggregate.answer_accuracy)}</td><td>{latency(run.aggregate.p50_latency_ms)}</td><td>{metric(run.aggregate.avg_context_tokens)}</td><td>{percent(run.aggregate.recall_at_k)}</td></tr>)}</tbody></table></div></section>
}

function describe(profile: RetrievalProfile) { return `${profile.mode} / Top${profile.top_k} / Candidate${profile.candidate_pool} / Rerank ${profile.rerank_enabled ? 'On' : 'Off'} / RRF${profile.rrf_k} / Dedupe ${profile.section_dedupe ? 'On' : 'Off'}` }
