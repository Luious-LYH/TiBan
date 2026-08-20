import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Layout } from './components/Layout'

const AgentWorkbench = lazy(() => import('./pages/AgentWorkbench').then((module) => ({ default: module.AgentWorkbench })))
const StudyCenter = lazy(() => import('./pages/StudyCenter').then((module) => ({ default: module.StudyCenter })))
const ModelHub = lazy(() => import('./pages/ModelHub').then((module) => ({ default: module.ModelHub })))

function App() {
  return <BrowserRouter><Layout><RouteFrame /></Layout></BrowserRouter>
}

function RouteFrame() {
  const location = useLocation()
  return (
    <ErrorBoundary resetKey={location.pathname}>
      <Suspense fallback={<div className="v21-route-loading" aria-label="页面加载中"><span /></div>}>
        <Routes>
          <Route path="/" element={<Navigate to={location.search.includes('case=') ? `/workbench${location.search}` : '/study'} replace />} />
          <Route path="/workbench" element={<AgentWorkbench />} />
          <Route path="/study" element={<StudyCenter />} />
          <Route path="/lab" element={<ModelHub />} />
          <Route path="/models" element={<Navigate to="/lab" replace />} />
          <Route path="/agent" element={<Navigate to="/workbench" replace />} />
          <Route path="/practice" element={<Navigate to="/study" replace />} />
          <Route path="/training" element={<Navigate to="/study" replace />} />
          <Route path="*" element={<Navigate to="/study" replace />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}

export default App
