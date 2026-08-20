import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Bot, CheckCircle2, FileText, ScanSearch, Sparkles } from 'lucide-react'
import { Card, SafetyNotice, Tag } from '../components/Primitives'
import { v3Api, v3DemoState, v3SafetyNotice } from '../lib/v3Api'
import type { PracticeState } from '../lib/types'

export function Dashboard() {
  const [practice, setPractice] = useState<PracticeState>(v3DemoState)

  useEffect(() => {
    v3Api.practiceState().then(setPractice).catch(() => setPractice(v3DemoState))
  }, [])

  const nextCase = practice.next_plan?.[0]

  return (
    <div className="page-stack v3-page golden-home">
      <section className="v3-home-hero golden-home-hero">
        <div className="golden-home-copy">
          <Tag tone="green">Golden Demo · 公开教学病例</Tag>
          <h2>从一张内镜图像开始，完成一次可追溯的 Agent 带教</h2>
          <p>观察图像并圈画重点，提交你的判断；辅导 Agent 会组织事实证据、解释错因、记录画像影响，并推荐下一步研修任务。</p>
          <div className="v3-hero-actions">
            <Link className="button primary golden-primary-cta" to="/practice?mode=practice&view=daily">
              <Sparkles size={17} /> 开始演示病例 <ArrowRight size={17} />
            </Link>
          </div>
          <small className="golden-hero-note">约 3 分钟 · 无需配置模型 · Provider 不可用时会明确标注规则回退</small>
        </div>
        <div className="golden-case-preview" aria-label="演示病例流程">
          <span className="golden-preview-kicker">本次演示</span>
          <strong>{nextCase?.label || '图像证据识别与表达训练'}</strong>
          <p>{nextCase?.reason || '优先巩固图像证据与题干前提之间的关系。'}</p>
          <div className="golden-preview-steps">
            <div><ScanSearch size={18} /><span><b>观察</b><small>图像与圈画</small></span></div>
            <div><Bot size={18} /><span><b>执行</b><small>评分与证据</small></span></div>
            <div><CheckCircle2 size={18} /><span><b>沉淀</b><small>画像与下一题</small></span></div>
          </div>
        </div>
      </section>

      <section className="golden-proof-band" aria-label="Agent 能力说明">
        <div><Bot size={20} /><span><strong>上下文辅导</strong><small>结合当前病例、作答与圈画进行追问</small></span></div>
        <div><ScanSearch size={20} /><span><strong>事实级复盘</strong><small>逐条呈现观察事实、依据与支持状态</small></span></div>
        <div><FileText size={20} /><span><strong>同病例交接</strong><small>研修完成后可进入医生复核前报告辅助</small></span></div>
      </section>

      <Card className="golden-transparency-card">
        <div>
          <Tag tone={practice.api_source === 'backend' ? 'green' : 'amber'}>{practice.api_source === 'backend' ? '后端已连接' : '演示回退数据'}</Tag>
          <h3>每一步都有“技术收据”</h3>
          <p>提交后可查看执行来源、事实证据、画像是否更新和下一步推荐；不把规则结果伪装成模型推理。</p>
        </div>
        <Link className="text-link" to="/report">了解医生复核前报告辅助 <ArrowRight size={15} /></Link>
      </Card>

      <SafetyNotice text={practice.safety_notice || v3SafetyNotice} />
    </div>
  )
}
