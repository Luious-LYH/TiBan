import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BookOpen,
  Calendar,
  CheckCircle2,
  Clock,
  Flame,
  TrendingUp,
  ArrowRight,
} from 'lucide-react'
import { v3Api } from '../lib/v3Api'
import type { QuestionBank } from '../lib/types.v2.2.2'
import { adaptQuestionBankFromBackend } from '../lib/adapters.v2.2.2'

export function Overview() {
  const navigate = useNavigate()
  const [banks, setBanks] = useState<QuestionBank[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 今日学习数据（模拟，后续接入真实 API）
  const todayCompleted = 3
  const todayTarget = 5
  const reviewDue = 7
  const streak = 4

  useEffect(() => {
    let mounted = true
    setLoading(true)
    setError(null)

    // 调用真实 API 获取题库摘要
    fetch('/api/question-banks')
      .then(res => res.json())
      .then(data => {
        if (!mounted) return

        // 适配后端数据
        const adaptedBanks = (data.banks || []).map(adaptQuestionBankFromBackend)
        setBanks(adaptedBanks)
      })
      .catch(err => {
        if (!mounted) return
        console.error('Failed to load question banks:', err)
        setError('加载题库失败，请稍后重试')
      })
      .finally(() => {
        if (mounted) setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [])

  const handleBankClick = (bankId: string) => {
    navigate(`/practice?bank_id=${bankId}`)
  }

  if (loading) {
    return (
      <div className="container" style={{ paddingTop: '80px' }}>
        <div className="loading">
          <div className="spinner" />
          <span>加载中...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container" style={{ paddingTop: '80px' }}>
        <div className="error-state">
          <p>{error}</p>
          <button className="btn btn-secondary" onClick={() => window.location.reload()}>
            重新加载
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="container" style={{ paddingTop: '24px', paddingBottom: '48px' }}>
      {/* 今日任务卡片 */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h2 className="text-2xl font-semibold" style={{ marginBottom: '16px' }}>
          今日学习
        </h2>

        <div className="grid gap-md" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
          <div className="flex flex-col gap-sm">
            <div className="flex items-center gap-sm text-muted">
              <CheckCircle2 size={16} />
              <span className="text-sm">已完成</span>
            </div>
            <div className="text-2xl font-bold text-primary">
              {todayCompleted} / {todayTarget}
            </div>
            <div className="text-sm text-muted">题</div>
          </div>

          <div className="flex flex-col gap-sm">
            <div className="flex items-center gap-sm text-muted">
              <Clock size={16} />
              <span className="text-sm">待复习</span>
            </div>
            <div className="text-2xl font-bold">{reviewDue}</div>
            <div className="text-sm text-muted">题</div>
          </div>

          <div className="flex flex-col gap-sm">
            <div className="flex items-center gap-sm text-muted">
              <Flame size={16} />
              <span className="text-sm">连续学习</span>
            </div>
            <div className="text-2xl font-bold">{streak}</div>
            <div className="text-sm text-muted">天</div>
          </div>

          <div className="flex flex-col gap-sm">
            <div className="flex items-center gap-sm text-muted">
              <TrendingUp size={16} />
              <span className="text-sm">本周正确率</span>
            </div>
            <div className="text-2xl font-bold">78%</div>
            <div className="text-sm text-muted">12 题</div>
          </div>
        </div>
      </div>

      {/* 题库列表 */}
      <h2 className="text-xl font-semibold" style={{ marginBottom: '16px' }}>
        题库
      </h2>

      {banks.length === 0 ? (
        <div className="empty-state">
          <BookOpen size={48} />
          <p className="font-medium">暂无题库</p>
          <p className="text-sm">请先导入题库后再开始练习</p>
          <button
            className="btn btn-primary"
            onClick={() => navigate('/banks')}
            style={{ marginTop: '16px' }}
          >
            去导入题库
          </button>
        </div>
      ) : (
        <div className="grid gap-lg" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
          {banks.map(bank => (
            <div
              key={bank.id}
              className="card card-hover"
              onClick={() => handleBankClick(bank.id)}
            >
              <div className="flex flex-col gap-md">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-semibold">{bank.name}</h3>
                    <p className="text-sm text-muted" style={{ marginTop: '4px' }}>
                      {bank.body_parts.join(' / ')}
                    </p>
                  </div>
                  <ArrowRight size={20} className="text-muted" />
                </div>

                <div className="flex items-center gap-sm flex-wrap">
                  {Object.entries(bank.question_type_counts).map(([type, count]) => (
                    <span key={type} className="badge badge-neutral">
                      {type} {count}
                    </span>
                  ))}
                </div>

                <div style={{ marginTop: '8px' }}>
                  <div className="flex justify-between text-sm" style={{ marginBottom: '8px' }}>
                    <span className="text-muted">进度</span>
                    <span className="font-medium">
                      {bank.completed} / {bank.total}
                    </span>
                  </div>
                  <div
                    style={{
                      height: '6px',
                      background: 'var(--panel-soft)',
                      borderRadius: '999px',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${bank.progress}%`,
                        background: 'var(--primary)',
                        transition: 'width 0.3s ease',
                      }}
                    />
                  </div>
                </div>

                <button className="btn btn-primary">
                  开始练习
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 最近记录 */}
      {banks.length > 0 && (
        <div className="card" style={{ marginTop: '32px' }}>
          <h3 className="text-lg font-semibold" style={{ marginBottom: '16px' }}>
            最近记录
          </h3>
          <div className="flex flex-col gap-sm">
            <div className="flex items-center justify-between" style={{ padding: '12px', background: 'var(--panel-soft)', borderRadius: 'var(--radius-md)' }}>
              <div className="flex items-center gap-md">
                <Calendar size={16} className="text-muted" />
                <span className="text-sm">今天 14:30</span>
                <span className="text-sm text-muted">食管基础</span>
              </div>
              <span className="badge badge-primary">正确</span>
            </div>
            <div className="flex items-center justify-between" style={{ padding: '12px', background: 'var(--panel-soft)', borderRadius: 'var(--radius-md)' }}>
              <div className="flex items-center gap-md">
                <Calendar size={16} className="text-muted" />
                <span className="text-sm">今天 10:15</span>
                <span className="text-sm text-muted">胃部观察</span>
              </div>
              <span className="badge badge-warning">错误</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
