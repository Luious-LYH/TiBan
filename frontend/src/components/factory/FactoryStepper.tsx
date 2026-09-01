const stages = [
  ['queued', '资料'],
  ['parsing', '解析'],
  ['generating', '生成'],
  ['ready_for_review', '审核'],
  ['published', '入库'],
] as const

export function FactoryStepper({ stage }: { stage: string }) {
  const stageMap: Record<string, number> = { queued: 0, parsing: 1, indexing: 1, generating: 2, judging: 3, repairing: 3, ready_for_review: 3, published: 4 }
  const currentIndex = stageMap[stage] ?? 0
  return <ol className="factory-stepper" aria-label="题目生成进度">{stages.map(([value, label], index) => <li className={index < currentIndex ? 'is-complete' : index === currentIndex ? 'is-current' : ''} key={value}><span>{index < currentIndex ? '✓' : index + 1}</span><small>{label}</small></li>)}</ol>
}
