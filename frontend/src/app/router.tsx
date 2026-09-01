import { Navigate, Route, Routes } from 'react-router-dom'
import { FactoryStudio } from '../components/factory/FactoryStudio'
import { PreviewPage } from '../components/layout/PreviewPage'
import { EvaluationPage } from '../pages/evaluation/EvaluationPage'
import { OverviewPage } from '../pages/overview/OverviewPage'
import { BanksPage } from '../pages/banks/BanksPage'
import { PracticePage } from '../pages/practice/PracticePage'
import { SettingsPage } from '../pages/settings/SettingsPage'

function FactoryPage() {
  return <div data-testid="factory-page"><FactoryStudio /></div>
}

export function AppRouter() {
  return <Routes>
    <Route path="/" element={<OverviewPage />} />
    <Route path="/banks" element={<BanksPage />} />
    <Route path="/practice" element={<PracticePage />} />
    <Route path="/eval" element={<EvaluationPage />} />
    <Route path="/factory" element={<FactoryPage />} />
    <Route path="/tutor" element={<PreviewPage eyebrow="智能辅导" title="题目辅导" description="围绕当前题目、学习阶段和可用资料进行受控对话。" capability="常驻智能辅导将从练习工作台中继续你的上下文。" nextPath="/practice" nextLabel="进入练习工作台" />} />
    <Route path="/knowledge" element={<PreviewPage eyebrow="知识库" title="资料库" description="管理经过许可的教学资料，并为题目和辅导提供可追溯的证据。" capability="资料库接入与来源治理正在准备中。" nextPath="/knowledge/search" nextLabel="查看检索工作台" />} />
    <Route path="/knowledge/search" element={<PreviewPage eyebrow="知识库" title="检索工作台" description="检查检索边界、来源片段和回答前的证据链。" capability="检索工作台将在 RAG 只读投影完成后接入。" nextPath="/practice" nextLabel="回到练习工作台" />} />
    <Route path="/settings" element={<SettingsPage />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
}
