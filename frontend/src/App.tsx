import { lazy, Suspense } from 'react'
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom'
import { AlertTriangle, ArrowRight } from 'lucide-react'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Layout } from './components/Layout'
import { Card } from './components/Primitives'

const Dashboard = lazy(() => import('./pages/Dashboard').then((module) => ({ default: module.Dashboard })))
const ModelHub = lazy(() => import('./pages/ModelHub').then((module) => ({ default: module.ModelHub })))
const PhysicianProfile = lazy(() =>
  import('./pages/PhysicianProfile').then((module) => ({ default: module.PhysicianProfile })),
)
const ReportDraft = lazy(() => import('./pages/ReportDraft').then((module) => ({ default: module.ReportDraft })))
const TrainingCenter = lazy(() => import('./pages/TrainingCenter').then((module) => ({ default: module.TrainingCenter })))
const DeliveryEvidence = lazy(() => import('./pages/DeliveryEvidence').then((module) => ({ default: module.DeliveryEvidence })))

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <RouteFrame />
      </Layout>
    </BrowserRouter>
  )
}

function RouteFrame() {
  const location = useLocation()
  return (
    <ErrorBoundary resetKey={location.pathname}>
      <Suspense fallback={<RouteLoading />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/models" element={<ModelHub />} />
          <Route path="/practice" element={<TrainingCenter />} />
          <Route path="/training" element={<TrainingCenter />} />
          <Route path="/report" element={<ReportDraft />} />
          <Route path="/profile" element={<PhysicianProfile />} />
          <Route path="/delivery" element={<DeliveryEvidence />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}

function RouteLoading() {
  return (
    <div className="route-loading" aria-label="页面加载中">
      <span />
    </div>
  )
}

function NotFound() {
  return (
    <Card className="route-guard-page">
      <AlertTriangle size={34} />
      <div>
        <span className="eyebrow">页面未找到</span>
        <h2>这个入口已合并到主流程</h2>
        <p>当前版本聚焦模型评估、医生研修、报告辅助和能力画像。</p>
        <Link className="button primary" to="/">
          回到首页 <ArrowRight size={17} />
        </Link>
      </div>
    </Card>
  )
}

export default App
