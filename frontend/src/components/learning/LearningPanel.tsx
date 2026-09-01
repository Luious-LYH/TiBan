import { CalendarClock, Target } from 'lucide-react'
import { useQuery, useMutation } from '@tanstack/react-query'

import { getMentorPlan, submitFsrsReview } from '../../api/client'
import type { ReviewCard } from '../../api/client'

export function LearningPanel({ questionId }: { questionId: string }) {
  const mentor = useQuery({ queryKey: ['mentor-plan'], queryFn: () => getMentorPlan() })
  const review = useMutation({ mutationFn: (rating: 'Again' | 'Hard' | 'Good' | 'Easy') => submitFsrsReview(questionId, rating) })
  const card = review.data as ReviewCard | undefined
  return <section className="s1-learning-panel" data-testid="learning-panel">
    <div><span className="s1-kicker">复习调度</span><h3><CalendarClock size={16} />用真实调度器安排下一次复习</h3><p>本次提交已先形成不可变作答记录，再由服务端更新掌握度与复习卡片。</p></div>
    <div className="s1-review-buttons">{(['Again', 'Hard', 'Good', 'Easy'] as const).map((rating) => <button key={rating} className="s1-button s1-button-light" disabled={review.isPending} onClick={() => review.mutate(rating)}>{({ Again: '重来', Hard: '困难', Good: '良好', Easy: '轻松' } as const)[rating]}</button>)}</div>
    {card && <small className="s1-learning-receipt">状态 {card.state} · 下次复习 {new Date(card.due_at).toLocaleString()} · 稳定度 {card.stability?.toFixed(2) ?? '—'} · 可回忆度 {card.retrievability?.toFixed(2) ?? '—'}</small>}
    {mentor.data && <div className="s1-mentor"><strong><Target size={15} />下一步建议：{mentor.data.focus}</strong><p>{mentor.data.steps[0]?.title}</p><small>待复习 {mentor.data.due_review_count} · 最近错误 {mentor.data.recent_errors.join('、') || '暂无'}</small></div>}
  </section>
}
