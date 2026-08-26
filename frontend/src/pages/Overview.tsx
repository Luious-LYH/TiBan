import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  BookOpen,
  Calendar,
  CheckCircle2,
  Clock,
  Flame,
  TrendingUp,
} from 'lucide-react'
import { v3Api } from '../lib/v3Api'
import type { PracticeState } from '../lib/types'

interface BankSummary {
  bankId: string
  name: string
  bodyPart: string
  totalQuestions: number
  completedQuestions: number
  progress: number
  questionTypes: string[]
  lastPracticeAt?: string
}

export function Overview() {
  const navigate = useNavigate()
  const [state, setState] = useState<PracticeState | null>(null)
  const [banks, setBanks] = useState<BankSummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    setLoading(true)
    Promise.all([
      v3Api.practiceState(),
      // 模拟题库摘要，后续接入真实 API
      Promise.resolve([
        {
          bankId: 'esophagus-teaching',
          name: '食管基础',
          bodyPart: '食管',
          totalQuestions: 42,
          completedQuestions: 29,
          progress: 68,
          questionTypes: ['单选', '判断', '简答'],
          lastPracticeAt: '2 小时前',
        },
        {
          bankId: 'stomach-teaching',
          name: '胃部观察',
          bodyPart: '胃',
          totalQuestions: 38,
          completedQuestions: 19,
          progress: 51,
          questionTypes: ['单选', '多选', '图文'],
          lastPracticeAt: '昨天',
        },
        {
          bankId: 'small-intestine-teaching',
          name: '小肠胶囊',
          bodyPart: '小肠',
          totalQuestions: 26,
          completedQuestions: 5,
          progress: 20,
          questionTypes: ['判断', '简答'],
          lastPracticeAt: '3 天前',
        },
      ] as BankSummary[]),
    ])
      .then(([nextState, nextBanks]) => {
        if (!mounted) return
        setState(nextState)
        setBanks(nextBanks)
      })
      .catch(() => {
        if (!mounted) return
      })
      .finally(() => {
        if (mounted) setLoading(false)
      })
    return () => {
      mounted = false
    }
  }, [])

  const todayCompleted = (state as any)?.today_completed ?? 0
  const todayTarget = 5
  const reviewDue = (state as any)?.wrong_cases?.length ?? 0
  const weekCorrectRate = state ? Math.round(((state as any).total_correct / ((state as any).total_answered || 1)) * 100) : 0
  const streak = 4 // 模拟数据

  const handleBankClick = (bankId: string) => {
    navigate(`/practice?bank_id=${bankId}`)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-neutral-500">加载中...</div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* 问候和今日目标 */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold mb-2">早上好</h1>
        <p className="text-neutral-600">
          今天完成 {todayTarget} 道题即可保持学习节奏
        </p>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={<CheckCircle2 className="w-5 h-5" />}
          label="今日任务"
          value={`${todayCompleted}/${todayTarget}`}
          color="emerald"
        />
        <StatCard
          icon={<Clock className="w-5 h-5" />}
          label="待复习"
          value={reviewDue}
          color="amber"
        />
        <StatCard
          icon={<TrendingUp className="w-5 h-5" />}
          label="本周正确率"
          value={`${weekCorrectRate}%`}
          color="blue"
        />
        <StatCard
          icon={<Flame className="w-5 h-5" />}
          label="连续天数"
          value={streak}
          color="orange"
        />
      </div>

      {/* 快速开始 */}
      <div className="mb-8">
        <h2 className="text-lg font-medium mb-4">快速开始</h2>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => navigate('/practice')}
            className="px-6 py-3 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
          >
            继续上次练习
          </button>
          <button
            onClick={() => navigate('/practice?mode=review')}
            className="px-6 py-3 bg-white border border-neutral-300 text-neutral-700 rounded-lg hover:bg-neutral-50 transition-colors"
          >
            开始到期复习
          </button>
        </div>
      </div>

      {/* 我的题库 */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium">我的题库</h2>
          <Link
            to="/banks"
            className="text-sm text-emerald-600 hover:text-emerald-700 flex items-center gap-1"
          >
            查看全部
            <span>→</span>
          </Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {banks.map((bank) => (
            <BankCard
              key={bank.bankId}
              bank={bank}
              onClick={() => handleBankClick(bank.bankId)}
            />
          ))}
          <button
            onClick={() => navigate('/banks?action=import')}
            className="h-[180px] border-2 border-dashed border-neutral-300 rounded-xl flex flex-col items-center justify-center gap-2 hover:border-emerald-500 hover:bg-emerald-50/50 transition-colors group"
          >
            <BookOpen className="w-8 h-8 text-neutral-400 group-hover:text-emerald-600" />
            <span className="text-sm text-neutral-600 group-hover:text-emerald-700">
              导入题库
            </span>
          </button>
        </div>
      </div>

      {/* 最近练习 */}
      {state && (state as any).recent_cases && (state as any).recent_cases.length > 0 && (
        <div>
          <h2 className="text-lg font-medium mb-4">最近练习</h2>
          <div className="space-y-2">
            {(state as any).recent_cases.slice(0, 5).map((item: any, idx: number) => (
              <div
                key={idx}
                className="flex items-center gap-3 p-3 bg-white border border-neutral-200 rounded-lg hover:border-neutral-300 transition-colors"
              >
                <Calendar className="w-4 h-4 text-neutral-400" />
                <span className="text-sm text-neutral-700">
                  {item.title || '练习记录'} - {item.last_review || '最近'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: string | number
  color: 'emerald' | 'amber' | 'blue' | 'orange'
}

function StatCard({ icon, label, value, color }: StatCardProps) {
  const colorClasses = {
    emerald: 'bg-emerald-50 text-emerald-600',
    amber: 'bg-amber-50 text-amber-600',
    blue: 'bg-blue-50 text-blue-600',
    orange: 'bg-orange-50 text-orange-600',
  }

  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-6">
      <div className={`inline-flex p-2 rounded-lg ${colorClasses[color]} mb-3`}>
        {icon}
      </div>
      <div className="text-2xl font-semibold mb-1">{value}</div>
      <div className="text-sm text-neutral-600">{label}</div>
    </div>
  )
}

interface BankCardProps {
  bank: BankSummary
  onClick: () => void
}

function BankCard({ bank, onClick }: BankCardProps) {
  return (
    <div
      onClick={onClick}
      className="h-[180px] bg-gradient-to-br from-white to-neutral-50 border border-neutral-200 rounded-xl p-5 cursor-pointer hover:shadow-lg hover:-translate-y-0.5 transition-all"
    >
      <div className="flex items-start justify-between mb-3">
        <BookOpen className="w-6 h-6 text-emerald-600" />
        <span className="text-xs px-2 py-1 bg-emerald-100 text-emerald-700 rounded-full">
          {bank.bodyPart}
        </span>
      </div>
      <h3 className="text-base font-medium mb-2">{bank.name}</h3>
      <div className="text-sm text-neutral-600 mb-3">
        {bank.totalQuestions} 题 · {bank.progress}%
      </div>
      <div className="w-full bg-neutral-200 rounded-full h-1.5 mb-3">
        <div
          className="bg-emerald-600 h-1.5 rounded-full transition-all"
          style={{ width: `${bank.progress}%` }}
        />
      </div>
      <div className="flex flex-wrap gap-1">
        {bank.questionTypes.map((type) => (
          <span
            key={type}
            className="text-xs px-2 py-0.5 bg-neutral-100 text-neutral-600 rounded"
          >
            {type}
          </span>
        ))}
      </div>
      {bank.lastPracticeAt && (
        <div className="text-xs text-neutral-500 mt-2">
          最近练习 {bank.lastPracticeAt}
        </div>
      )}
    </div>
  )
}
