import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Layout } from './components/Layout'

// v2.2.2 四模块页面（重写版）
const Overview = lazy(() => import('./pages/Overview.v2.2.2').then((module) => ({ default: module.Overview })))
const QuestionBanks = lazy(() => import('./pages/QuestionBanks.v2.2.2').then((module) => ({ default: module.QuestionBanks })))
const PracticeWorkspace = lazy(() => import('./pages/PracticeWorkspace.v2.2.2').then((module) => ({ default: module.PracticeWorkspace })))
const ModelEvaluation = lazy(() => import('./pages/ModelEvaluation.v2.2.2').then((module) => ({ default: module.ModelEvaluation })))

// 旧页面保留兼容
const AgentWorkbench = lazy(() => import('./pages/AgentWorkbench').then((module) => ({ default: module.AgentWorkbench })))
const StudyCenter = lazy(() => import('./pages/StudyCenter').then((module) => ({ default: module.StudyCenter })))

function App() {
  return <BrowserRouter><Layout><RouteFrame /></Layout></BrowserRouter>
}

function RouteFrame() {
  const location = useLocation()
  return (
    <ErrorBoundary resetKey={location.pathname}>
      <Suspense fallback={<div className="v21-route-loading" aria-label="页面加载中"><span /></div>}>
        <Routes>
          {/* v2.2.1 新路由：四模块架构 */}
          <Route path="/" element={<Overview />} />
          <Route path="/banks" element={<QuestionBanks />} />
          <Route path="/practice" element={<PracticeWorkspace />} />
          <Route path="/eval" element={<ModelEvaluation />} />

          {/* 旧路由兼容 */}
          <Route path="/workbench" element={<AgentWorkbench />} />
          <Route path="/study" element={<StudyCenter />} />
          <Route path="/lab" element={<Navigate to="/eval" replace />} />
          <Route path="/models" element={<Navigate to="/eval" replace />} />
          <Route path="/agent" element={<Navigate to="/workbench" replace />} />
          <Route path="/training" element={<Navigate to="/banks" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}

export default App
