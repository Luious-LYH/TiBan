import { useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
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
          <Route path="/false-premise" element={<FalsePremiseTraining />} />
          <Route path="/report" element={<ReportDraft />} />
          <Route path="/profile" element={<PhysicianProfile />} />
          <Route path="/card" element={<PatientCard />} />
          <Route path="/models" element={<ModelHub />} />
          <Route path="/skills" element={<SkillsCenter />} />
          <Route path="/audit" element={<AuditPanel />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
