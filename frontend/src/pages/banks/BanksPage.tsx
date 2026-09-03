import { ArrowRight, BookOpen, Search, SlidersHorizontal, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { getDomains, getQuestionBanks } from '../../api/client'
import { SessionBuilder } from '../../components/practice/SessionBuilder'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'

const typeLabels: Record<string, string> = { single_choice: '单选', multiple_choice: '多选', true_false: '判断', short_answer: '简答' }

export function BanksPage() {
  const [domain, setDomain] = useState('all')
  const [search, setSearch] = useState('')
  const [type, setType] = useState('all')
  const domainsQuery = useQuery({ queryKey: ['domains'], queryFn: getDomains, staleTime: 5 * 60 * 1000 })
  const banksQuery = useQuery({ queryKey: ['question-banks', domain], queryFn: () => getQuestionBanks('demo_learner', domain === 'all' ? undefined : domain) })
  const banks = useMemo(() => (banksQuery.data ?? []).filter((bank) => {
    const matchesSearch = !search.trim() || `${bank.name} ${bank.description}`.toLowerCase().includes(search.trim().toLowerCase())
    return matchesSearch && (type === 'all' || Boolean(bank.question_type_counts[type]))
  }), [banksQuery.data, search, type])

  if (banksQuery.isPending) return <LoadingState label="正在读取题库目录…" />
  if (banksQuery.isError) return <ErrorState message={banksQuery.error.message} onRetry={() => void banksQuery.refetch()} />

  return <div className="catalog-page" data-testid="banks-page">
    <header className="catalog-header"><div><h1>题库</h1><p>选择一个题库，开始本次练习。</p></div><Link className="catalog-factory-link" to="/factory"><Sparkles size={16} />题库导入</Link></header>
    <section className="catalog-toolbar" aria-label="题库筛选">
      <label className="catalog-search"><Search size={17} /><span className="s1-visually-hidden">搜索题库</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索题库…" /></label>
      <label className="catalog-select"><BookOpen size={16} /><span className="s1-visually-hidden">选择学习领域</span><select aria-label="选择学习领域" value={domain} onChange={(event) => { setDomain(event.target.value); setSearch(''); setType('all') }}><option value="all">全部领域</option>{(domainsQuery.data ?? []).map((item) => <option key={item.domain_id} value={item.domain_id}>{item.display_name}</option>)}</select></label>
      <label className="catalog-select"><SlidersHorizontal size={16} /><span className="s1-visually-hidden">按题型筛选</span><select aria-label="按题型筛选" value={type} onChange={(event) => setType(event.target.value)}><option value="all">全部题型</option>{Object.entries(typeLabels).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
    </section>
    {banks.length === 0 ? <section className="catalog-empty"><EmptyState title="没有匹配的题库" detail="试试清空搜索或切换题型筛选。" /></section> : <section className="catalog-list">{banks.map((bank) => <article className="catalog-row" key={bank.bank_id}>
      <span className="catalog-row-icon"><BookOpen size={18} /></span>
      <div className="catalog-row-copy"><Link to={`/banks/${encodeURIComponent(bank.bank_id)}`}><h2>{displayName(bank.name)}</h2></Link><p>{learnerBankDescription(bank.bank_id, bank.description)}</p><div><span>{bank.question_count} 题</span><span>已做 {bank.completed_count}</span><span>错题 {bank.incorrect_count}</span><span>标记 {bank.marked_count}</span>{Object.entries(bank.question_type_counts).map(([key, count]) => <span key={key}>{count} {typeLabels[key] ?? key}</span>)}</div></div>
      <div className="catalog-row-progress"><span>{bank.completed_count} / {bank.question_count}</span><i><b style={{ width: `${Math.round(bank.progress * 100)}%` }} /></i></div>
      <div className="catalog-row-actions"><Link to={`/banks/${encodeURIComponent(bank.bank_id)}`}>查看题目 <ArrowRight size={14} /></Link><SessionBuilder bankId={bank.bank_id} bankName={displayName(bank.name)} availableCounts={bank} /></div>
    </article>)}</section>}
  </div>
}

function displayName(name: string) { return name.replace(/医疗\s*\/\s*消化内镜\s*·\s*Factory\s*生成题草稿库/g, '医疗 / 消化内镜 · 资料生成题库').replace(/\s*[（(]本地导入[）)]/g, '').trim() }
function learnerBankDescription(bankId: string, fallback: string) { const summaries: Record<string, string> = { 'bank-cmb-exam-real': '覆盖医学基础与临床知识的综合练习题。', 'bank-cmexam-real': '覆盖医学基础与临床知识的综合练习题。', 'bank-kvasir-vqa-curated': '通过内镜图像观察训练可见事实判断。' }; return summaries[bankId] ?? fallback.replace(/本地导入/g, '').trim() }
