import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { getEvaluationCatalog } from '../../api/client'
import { ErrorState } from '../../components/shared/AsyncState'
import { Tabs } from '../../components/ui/Tabs'
import { ModelEvaluationTab } from './ModelEvaluationTab'
import { RagEvaluationTab } from './RagEvaluationTab'

function errorMessage(error: unknown) { return error instanceof Error ? error.message : '无法读取评测实验室配置。' }

export function EvaluationPage() {
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') === 'rag' ? 'rag' : 'model'
  const catalog = useQuery({ queryKey: ['evaluation-lab-catalog'], queryFn: getEvaluationCatalog, retry: false })
  return <div className="evaluation-workspace" data-testid="evaluation-page">
    <header className="evaluation-header"><div><h1>评测实验室</h1><p>冻结同一批题目与运行条件，用真实后台实验比较候选模型和检索方案。</p></div></header>
    <Tabs value={tab} onChange={(value) => setParams({ tab: value })} label="评测类型" items={[{ value: 'model', label: '模型评测' }, { value: 'rag', label: 'RAG 评测' }]} />
    {catalog.isError && <ErrorState message={errorMessage(catalog.error)} onRetry={() => void catalog.refetch()} />}
    {catalog.data && (tab === 'model' ? <ModelEvaluationTab catalog={catalog.data} /> : <RagEvaluationTab catalog={catalog.data} />)}
  </div>
}
