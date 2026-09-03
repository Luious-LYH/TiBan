import { Navigate, Route, Routes } from 'react-router-dom'
import { FactoryStudio } from '../components/factory/FactoryStudio'
import { EvaluationPage } from '../pages/evaluation/EvaluationPage'
import { OverviewPage } from '../pages/overview/OverviewPage'
import { BanksPage } from '../pages/banks/BanksPage'
import { BankDetailPage } from '../pages/banks/BankDetailPage'
import { PracticePage } from '../pages/practice/PracticePage'
import { ReviewPage } from '../pages/review/ReviewPage'
import { SettingsPage } from '../pages/settings/SettingsPage'
import { KnowledgePage } from '../pages/knowledge/KnowledgePage'
import { MentorPage } from '../pages/mentor/MentorPage'

function FactoryPage() {
  return <div data-testid="factory-page"><FactoryStudio /></div>
}

export function AppRouter() {
  return <Routes>
    <Route path="/" element={<OverviewPage />} />
    <Route path="/banks" element={<BanksPage />} />
    <Route path="/banks/:bankId" element={<BankDetailPage />} />
    <Route path="/practice" element={<PracticePage />} />
    <Route path="/review" element={<ReviewPage />} />
    <Route path="/eval" element={<EvaluationPage />} />
    <Route path="/factory" element={<FactoryPage />} />
    <Route path="/knowledge" element={<KnowledgePage />} />
    <Route path="/mentor" element={<MentorPage />} />
    <Route path="/settings" element={<SettingsPage />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
}
