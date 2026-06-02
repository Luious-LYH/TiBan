import { Suspense, lazy, useState } from 'react'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { AlertTriangle, ArrowRight } from 'lucide-react'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Layout } from './components/Layout'
import { Card } from './components/Primitives'
import type { Question, SubmissionResponse } from './lib/types'

const Dashboard = lazy(() => import('./pages/Dashboard').then((module) => ({ default: module.Dashboard })))
const TrainingCenter = lazy(() => import('./pages/TrainingCenter').then((module) => ({ default: module.TrainingCenter })))
const ErrorFeedback = lazy(() => import('./pages/ErrorFeedback').then((module) => ({ default: module.ErrorFeedback })))
const FalsePremiseTraining = lazy(() => import('./pages/FalsePremiseTraining').then((module) => ({ default: module.FalsePremiseTraining })))
const ReportDraft = lazy(() => import('./pages/ReportDraft').then((module) => ({ default: module.ReportDraft })))
const PhysicianProfile = lazy(() => import('./pages/PhysicianProfile').then((module) => ({ default: module.PhysicianProfile })))
const PatientCard = lazy(() => import('./pages/PatientCard').then((module) => ({ default: module.PatientCard })))
const ModelHub = lazy(() => import('./pages/ModelHub').then((module) => ({ default: module.ModelHub })))
const SkillsCenter = lazy(() => import('./pages/SkillsCenter').then((module) => ({ default: module.SkillsCenter })))
const AuditPanel = lazy(() => import('./pages/AuditPanel').then((module) => ({ default: module.AuditPanel })))

function App() {
  const [lastSubmission, setLastSubmission] = useState<SubmissionResponse | null>(null)
  const [lastQuestion, setLastQuestion] = useState<Question | null>(null)

  return (
    <BrowserRouter>
      <Layout>
        <ErrorBoundary>
          <Suspense fallback={<RouteLoading />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route
                path="/training"
                element={
                  <TrainingCenter
                    onSubmission={(submission, question) => {
                      setLastSubmission(submission)
                      setLastQuestion(question)
                    }}
                  />
                }
              />
              <Route path="/feedback" element={<ErrorFeedback submission={lastSubmission} question={lastQuestion} />} />
              <Route
                path="/false-premise"
                element={
                  <FalsePremiseTraining
                    onSubmission={(submission, question) => {
                      setLastSubmission(submission)
                      setLastQuestion(question)
                    }}
                  />
                }
              />
              <Route path="/report" element={<ReportDraft />} />
              <Route path="/profile" element={<PhysicianProfile />} />
              <Route path="/card" element={<PatientCard />} />
              <Route path="/models" element={<ModelHub />} />
              <Route path="/skills" element={<SkillsCenter />} />
              <Route path="/audit" element={<AuditPanel />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </Layout>
    </BrowserRouter>
  )
}

function RouteLoading() {
  return (
    <Card className="route-loading">
      <div className="loading-pulse" />
      <div>
        <span className="eyebrow">Loading workspace</span>
        <h2>正在载入训练工作区</h2>
        <p>按需加载页面模块，保持训练驾驶舱首屏轻量。</p>
      </div>
    </Card>
  )
}

function NotFound() {
  return (
    <Card className="fallback-page">
      <AlertTriangle size={34} />
      <div>
        <span className="eyebrow">Route fallback</span>
        <h2>未找到该训练工作区</h2>
        <p>当前路径没有对应模块。可以返回训练驾驶舱，继续刷题、报告训练或模型准入探测。</p>
        <Link className="button primary" to="/">
          回到训练驾驶舱 <ArrowRight size={17} />
        </Link>
      </div>
    </Card>
  )
}

export default App
