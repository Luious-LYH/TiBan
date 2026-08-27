import { Navigate, Route, Routes } from 'react-router-dom'
import { OverviewPage } from '../pages/overview/OverviewPage'
import { BanksPage } from '../pages/banks/BanksPage'
import { PracticePage } from '../pages/practice/PracticePage'
import { EvaluationPage } from '../pages/evaluation/EvaluationPage'

export function AppRouter() {
  return <Routes><Route path="/" element={<OverviewPage />} /><Route path="/banks" element={<BanksPage />} /><Route path="/practice" element={<PracticePage />} /><Route path="/eval" element={<EvaluationPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes>
}
