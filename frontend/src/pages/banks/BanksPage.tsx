import { ArrowRight, BookOpen, Search, SlidersHorizontal } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDomains, getQuestionBanks } from '../../api/client'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'
import { FactoryStudio } from '../../components/factory/FactoryStudio'

const typeLabels: Record<string, string> = { single_choice: '单选', multiple_choice: '多选', true_false: '判断', short_answer: '简答' }

export function BanksPage() {
  const [domain, setDomain] = useState('all')
  const domainsQuery = useQuery({ queryKey: ['domains'], queryFn: getDomains, staleTime: 5 * 60 * 1000 })
  const banksQuery = useQuery({ queryKey: ['question-banks', domain], queryFn: () => getQuestionBanks('demo_learner', domain === 'all' ? undefined : domain) })
  const [search, setSearch] = useState('')
  const [type, setType] = useState('all')

  const banks = useMemo(() => (banksQuery.data ?? []).filter((bank) => {
    const matchesSearch = !search.trim() || `${bank.name} ${bank.description} ${bank.body_parts.join(' ')}`.toLowerCase().includes(search.trim().toLowerCase())
    const matchesType = type === 'all' || Boolean(bank.question_type_counts[type])
    return matchesSearch && matchesType
  }), [banksQuery.data, search, type])

  if (banksQuery.isPending) return <LoadingState label="正在读取题库目录…" />
  if (banksQuery.isError) return <ErrorState message={banksQuery.error.message} onRetry={() => void banksQuery.refetch()} />

  return (
    <div className="s1-page" data-testid="banks-page">
      <section className="s1-page-intro"><div><span className="s1-kicker">QUESTION BANKS</span><h1>选择一个真实题库，开始练习。</h1><p>按题型和学习进度选择适合自己的练习。</p></div><span className="s1-source-pill">{banksQuery.data.length} 个题库</span></section>
      <section className="s1-card s1-toolbar" aria-label="题库筛选">
        <label className="s1-search"><Search size={17} /><span className="s1-visually-hidden">搜索题库</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索部位、题库名称…" /></label>
        <label className="s1-select"><BookOpen size={16} /><span className="s1-visually-hidden">选择学习领域</span><select aria-label="选择学习领域" value={domain} onChange={(event) => { setDomain(event.target.value); setSearch(''); setType('all') }}><option value="all">全部学习领域</option>{(domainsQuery.data ?? []).map((item) => <option key={item.domain_id} value={item.domain_id}>{item.display_name}</option>)}</select></label>
        <label className="s1-select"><SlidersHorizontal size={16} /><span className="s1-visually-hidden">按题型筛选</span><select value={type} onChange={(event) => setType(event.target.value)}><option value="all">全部题型</option>{Object.entries(typeLabels).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
      </section>
      {banks.length === 0 ? <section className="s1-card"><EmptyState title="没有匹配的题库" detail="试试清空搜索或切换题型筛选。" /></section> : <section className="s1-bank-grid">{banks.map((bank) => <article className="s1-card s1-bank-card" key={bank.bank_id}><div className="s1-bank-card-top"><span className="s1-bank-icon"><BookOpen size={18} /></span><span className="s1-source-pill">{bank.status === 'published' ? '已发布' : '草稿'}</span></div><h2>{bank.name}</h2><p>{learnerBankDescription(bank.bank_id, bank.description)}</p><div className="s1-bank-meta"><span>{bank.question_count} 道题</span><span>{bank.body_parts.join(' · ')}</span></div><div className="s1-type-breakdown">{Object.entries(bank.question_type_counts).map(([key, count]) => <span key={key}><b>{count}</b>{typeLabels[key] ?? key}</span>)}</div><div className="s1-progress-line"><span><i style={{ width: `${Math.round(bank.progress * 100)}%` }} /></span><small>{bank.completed_count} / {bank.question_count} 已完成</small></div><Link className="s1-button s1-button-primary s1-full-button" to={`/practice?bank_id=${encodeURIComponent(bank.bank_id)}`}>开始练习 <ArrowRight size={16} /></Link></article>)}</section>}
      <FactoryStudio />
      <p className="s1-safety">题库内容用于学习训练与复盘，请结合所选领域的课程资料和教师指导。</p>
    </div>
  )
}

function learnerBankDescription(bankId: string, fallback: string) {
  const summaries: Record<string, string> = {
    'bank-cmb-exam-real': '覆盖医学基础与临床知识的综合练习题。',
    'bank-cmexam-real': '覆盖医学基础与临床知识的综合练习题。',
    'bank-kvasir-vqa-curated': '通过内镜图像观察训练可见事实判断。',
  }
  return summaries[bankId] ?? fallback
}
