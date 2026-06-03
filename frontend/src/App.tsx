import { useState } from 'react'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { AlertTriangle, ArrowRight } from 'lucide-react'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Layout } from './components/Layout'
import { Card } from './components/Primitives'
import { AuditPanel } from './pages/AuditPanel'
import { Dashboard } from './pages/Dashboard'
import { ErrorFeedback } from './pages/ErrorFeedback'
import { FalsePremiseTraining } from './pages/FalsePremiseTraining'
import { ModelHub } from './pages/ModelHub'
import { PatientCard } from './pages/PatientCard'
import { PhysicianProfile } from './pages/PhysicianProfile'
import { ReportDraft } from './pages/ReportDraft'
import { SkillsCenter } from './pages/SkillsCenter'
import { TrainingCenter } from './pages/TrainingCenter'
import type { Question, SubmissionResponse } from './lib/types'

function App() {
  const [lastSubmission, setLastSubmission] = useState<SubmissionResponse | null>(null)
  const [lastQuestion, setLastQuestion] = useState<Question | null>(null)

  return (
    <BrowserRouter>
      <Layout>
        <ErrorBoundary>
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
        </ErrorBoundary>
      </Layout>
    </BrowserRouter>
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
