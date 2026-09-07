import { ArrowDown, ArrowRight, ArrowUp, BookOpen, GripVertical, Pencil, Search, Settings2, SlidersHorizontal, Sparkles, Trash2, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { deleteQuestionBank, getDomains, getQuestionBanks, reorderQuestionBanks, updateQuestionBank } from '../../api/client'
import type { QuestionBank } from '../../api/client'
import { SessionBuilder } from '../../components/practice/SessionBuilder'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'

const typeLabels: Record<string, string> = { single_choice: '单选', multiple_choice: '多选', true_false: '判断', short_answer: '简答' }

export function BanksPage() {
  const [domain, setDomain] = useState('all')
  const [search, setSearch] = useState('')
  const [type, setType] = useState('all')
  const [manageMode, setManageMode] = useState(false)
  const [draggedBankId, setDraggedBankId] = useState<string | null>(null)
  const [dropTargetBankId, setDropTargetBankId] = useState<string | null>(null)
  const [ordering, setOrdering] = useState(false)
  const [sortNotice, setSortNotice] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<QuestionBank | null>(null)
  const [editTarget, setEditTarget] = useState<QuestionBank | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [savingEdit, setSavingEdit] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const domainsQuery = useQuery({ queryKey: ['domains'], queryFn: getDomains, staleTime: 5 * 60 * 1000 })
  const banksQuery = useQuery({ queryKey: ['question-banks', domain], queryFn: () => getQuestionBanks('demo_learner', domain === 'all' ? undefined : domain) })
  const allBanks = useMemo(() => banksQuery.data ?? [], [banksQuery.data])
  const hasFilters = domain !== 'all' || Boolean(search.trim()) || type !== 'all'
  const canSort = manageMode && !hasFilters && allBanks.length > 1 && !ordering
  const banks = useMemo(() => allBanks.filter((bank) => {
    const matchesSearch = !search.trim() || `${bank.name} ${bank.description}`.toLowerCase().includes(search.trim().toLowerCase())
    return matchesSearch && (type === 'all' || Boolean(bank.question_type_counts[type]))
  }), [allBanks, search, type])

  useEffect(() => {
    function cancelPointerDrag() {
      setDraggedBankId(null)
      setDropTargetBankId(null)
    }
    window.addEventListener('pointerup', cancelPointerDrag)
    window.addEventListener('pointercancel', cancelPointerDrag)
    return () => {
      window.removeEventListener('pointerup', cancelPointerDrag)
      window.removeEventListener('pointercancel', cancelPointerDrag)
    }
  }, [])

  async function persistOrder(bankIds: string[]) {
    setOrdering(true)
    setActionError(null)
    setSortNotice(null)
    try {
      await reorderQuestionBanks(bankIds)
      await banksQuery.refetch()
      setSortNotice('题库顺序已保存。')
    } catch (reason) {
      setActionError((reason as Error).message)
    } finally {
      setOrdering(false)
      setDraggedBankId(null)
      setDropTargetBankId(null)
    }
  }

  function orderWithSwap(sourceBankId: string, targetBankId: string) {
    if (!canSort || sourceBankId === targetBankId) return
    const ids = allBanks.map((bank) => bank.bank_id)
    const sourceIndex = ids.indexOf(sourceBankId)
    const targetIndex = ids.indexOf(targetBankId)
    if (sourceIndex < 0 || targetIndex < 0) return
    const next = [...ids]
    const [moved] = next.splice(sourceIndex, 1)
    next.splice(targetIndex, 0, moved)
    void persistOrder(next)
  }

  function moveBank(bankId: string, direction: -1 | 1) {
    if (!canSort) return
    const ids = allBanks.map((bank) => bank.bank_id)
    const index = ids.indexOf(bankId)
    const targetIndex = index + direction
    if (index < 0 || targetIndex < 0 || targetIndex >= ids.length) return
    const next = [...ids]
    ;[next[index], next[targetIndex]] = [next[targetIndex], next[index]]
    void persistOrder(next)
  }

  if (banksQuery.isPending) return <LoadingState label="正在读取题库目录…" />
  if (banksQuery.isError) return <ErrorState message={banksQuery.error.message} onRetry={() => void banksQuery.refetch()} />

  return <div className="catalog-page" data-testid="banks-page">
    <header className="catalog-header"><div><h1>题库</h1><p>{manageMode ? '管理题库名称、说明、顺序与删除操作。' : '选择一个题库，开始本次练习。'}</p></div><div className="catalog-header-actions"><button className={`catalog-manage-toggle${manageMode ? ' is-active' : ''}`} type="button" onClick={() => { setManageMode((value) => !value); setSortNotice(null); setActionError(null) }}><Settings2 size={16} />{manageMode ? '完成管理' : '管理题库'}</button><Link className="catalog-factory-link" to="/factory"><Sparkles size={16} />题库导入</Link></div></header>
    <section className="catalog-toolbar" aria-label="题库筛选">
      <label className="catalog-search"><Search size={17} /><span className="s1-visually-hidden">搜索题库</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索题库…" /></label>
      <label className="catalog-select"><BookOpen size={16} /><span className="s1-visually-hidden">选择学习领域</span><select aria-label="选择学习领域" value={domain} onChange={(event) => { setDomain(event.target.value); setSearch(''); setType('all') }}><option value="all">全部领域</option>{(domainsQuery.data ?? []).map((item) => <option key={item.domain_id} value={item.domain_id}>{item.display_name}</option>)}</select></label>
      <label className="catalog-select"><SlidersHorizontal size={16} /><span className="s1-visually-hidden">按题型筛选</span><select aria-label="按题型筛选" value={type} onChange={(event) => setType(event.target.value)}><option value="all">全部题型</option>{Object.entries(typeLabels).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
    </section>
    {manageMode ? <div className={`catalog-order-hint${hasFilters ? ' is-filtered' : ''}`} role="status"><GripVertical size={16} />{hasFilters ? '清除搜索和筛选后可调整题库顺序。' : ordering ? '正在保存题库顺序…' : sortNotice ?? '按住题库行左侧六点手柄拖到目标位置，也可使用上移/下移；顺序会自动保存。'}</div> : null}
    {actionError && <p className="catalog-action-error" role="alert">{actionError}</p>}
    {banks.length === 0 ? <section className="catalog-empty"><EmptyState title="没有匹配的题库" detail="试试清空搜索或切换题型筛选。" /></section> : <section className="catalog-list">{banks.map((bank) => {
      const bankIndex = allBanks.findIndex((item) => item.bank_id === bank.bank_id)
      const isSortableRow = manageMode && !hasFilters
      return <article
        className={`catalog-row${isSortableRow ? ' is-sortable' : ''}${draggedBankId === bank.bank_id ? ' is-dragging' : ''}${dropTargetBankId === bank.bank_id ? ' is-drop-target' : ''}`}
        key={bank.bank_id}
        draggable={isSortableRow && !ordering}
        onDragStart={(event) => { if (!isSortableRow || ordering) return; setDraggedBankId(bank.bank_id); event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', bank.bank_id) }}
        onDragOver={(event) => { if (isSortableRow && draggedBankId && draggedBankId !== bank.bank_id) { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; setDropTargetBankId(bank.bank_id) } }}
        onDrop={(event) => { event.preventDefault(); const sourceBankId = event.dataTransfer.getData('text/plain') || draggedBankId; if (sourceBankId) orderWithSwap(sourceBankId, bank.bank_id) }}
        onPointerEnter={() => { if (isSortableRow && draggedBankId && draggedBankId !== bank.bank_id) setDropTargetBankId(bank.bank_id) }}
        onPointerUp={() => { if (isSortableRow && draggedBankId && draggedBankId !== bank.bank_id) orderWithSwap(draggedBankId, bank.bank_id) }}
        onDragEnd={() => { setDraggedBankId(null); setDropTargetBankId(null) }}
      >
      {isSortableRow ? <span className="catalog-sort-handle" role="button" tabIndex={0} title="按住拖动调整顺序" aria-label="拖动调整顺序" onPointerDown={(event) => { if (ordering) return; event.preventDefault(); setDraggedBankId(bank.bank_id); setDropTargetBankId(null) }}><GripVertical size={17} /></span> : null}
      <span className="catalog-row-icon"><BookOpen size={18} /></span>
      <div className="catalog-row-copy"><Link to={`/banks/${encodeURIComponent(bank.bank_id)}`}><h2>{displayName(bank.name)}</h2></Link><p>{learnerBankDescription(bank.bank_id, bank.description)}</p><div><span>{bank.question_count} 题</span><span>已做 {bank.completed_count}</span><span>错题 {bank.incorrect_count}</span><span>标记 {bank.marked_count}</span>{Object.entries(bank.question_type_counts).map(([key, count]) => <span key={key}>{count} {typeLabels[key] ?? key}</span>)}</div></div>
      <div className="catalog-row-progress"><span>{bank.completed_count} / {bank.question_count}</span><i><b style={{ width: `${Math.round(bank.progress * 100)}%` }} /></i></div>
      <div className={`catalog-row-actions${manageMode ? ' is-manage' : ''}`}>
        {isSortableRow ? <div className="catalog-row-sort-controls"><button type="button" title="上移" aria-label={`上移 ${displayName(bank.name)}`} disabled={!canSort || bankIndex <= 0} onClick={() => moveBank(bank.bank_id, -1)}><ArrowUp size={14} /></button><button type="button" title="下移" aria-label={`下移 ${displayName(bank.name)}`} disabled={!canSort || bankIndex < 0 || bankIndex >= allBanks.length - 1} onClick={() => moveBank(bank.bank_id, 1)}><ArrowDown size={14} /></button></div> : null}
        <Link to={`/banks/${encodeURIComponent(bank.bank_id)}`}>查看题目 <ArrowRight size={14} /></Link><SessionBuilder bankId={bank.bank_id} bankName={displayName(bank.name)} availableCounts={bank} />{manageMode ? <div className="catalog-row-manage-actions"><button className="catalog-edit-action" type="button" title="编辑题库" onClick={() => { setActionError(null); setSortNotice(null); setEditTarget(bank); setEditName(bank.name); setEditDescription(bank.description) }}><Pencil size={14} />编辑</button><button className="catalog-delete-action" type="button" title="删除题库" onClick={() => { setActionError(null); setSortNotice(null); setDeleteTarget(bank) }}><Trash2 size={14} />删除</button></div> : null}
      </div>
    </article>
    })}</section>}
    {editTarget && <div className="bank-edit-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target && !savingEdit) setEditTarget(null) }}><section className="bank-edit-dialog" role="dialog" aria-modal="true" aria-labelledby="bank-edit-title"><header><div><span className="catalog-dialog-kicker">题库管理</span><h2 id="bank-edit-title">编辑题库</h2></div><button type="button" aria-label="关闭" disabled={savingEdit} onClick={() => setEditTarget(null)}><X size={17} /></button></header><div className="bank-edit-fields"><label><span>题库名称</span><input value={editName} onChange={(event) => setEditName(event.target.value)} maxLength={200} /></label><label><span>题库说明</span><textarea value={editDescription} onChange={(event) => setEditDescription(event.target.value)} maxLength={1000} rows={4} /></label></div><footer><button type="button" disabled={savingEdit} onClick={() => setEditTarget(null)}>取消</button><button className="is-primary" type="button" disabled={savingEdit || !editName.trim()} onClick={() => void (async () => { setSavingEdit(true); setActionError(null); try { await updateQuestionBank(editTarget.bank_id, { name: editName.trim(), description: editDescription.trim() }); setEditTarget(null); await banksQuery.refetch() } catch (reason) { setActionError((reason as Error).message) } finally { setSavingEdit(false) } })()}>{savingEdit ? '正在保存…' : '保存修改'}</button></footer></section></div>}
    {deleteTarget && <div className="bank-delete-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target && !deleting) setDeleteTarget(null) }}><section className="bank-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="bank-delete-title"><header><span><Trash2 size={18} /></span><button type="button" aria-label="关闭" disabled={deleting} onClick={() => setDeleteTarget(null)}><X size={17} /></button></header><div><h2 id="bank-delete-title">删除题库？</h2><p>“{displayName(deleteTarget.name)}”及其题目、学习记录和评测关联会被删除。这个操作无法撤销；如需保留题目，请先导出原文件。</p></div><footer><button type="button" disabled={deleting} onClick={() => setDeleteTarget(null)}>取消</button><button className="is-danger" type="button" disabled={deleting} onClick={() => void (async () => { setDeleting(true); setActionError(null); try { await deleteQuestionBank(deleteTarget.bank_id); setDeleteTarget(null); await banksQuery.refetch() } catch (reason) { setActionError((reason as Error).message) } finally { setDeleting(false) } })()}>{deleting ? '正在删除…' : '确认删除'}</button></footer></section></div>}
  </div>
}

function displayName(name: string) { return name.replace(/医疗\s*\/\s*消化内镜\s*·\s*Factory\s*生成题草稿库/g, '医疗 / 消化内镜 · 资料生成题库').replace(/\s*[（(]本地导入[）)]/g, '').trim() }
function learnerBankDescription(bankId: string, fallback: string) { const summaries: Record<string, string> = { 'bank-cmb-exam-real': '覆盖医学基础与临床知识的综合练习题。', 'bank-cmexam-real': '覆盖医学基础与临床知识的综合练习题。', 'bank-kvasir-vqa-curated': '通过内镜图像观察训练可见事实判断。' }; return summaries[bankId] ?? fallback.replace(/本地导入/g, '').trim() }
