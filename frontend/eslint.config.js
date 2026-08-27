import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores([
    'dist',
    // Legacy routes and clients are deliberately quarantined.  The active
    // Stage 1/2 route tree lives under src/pages/{overview,banks,practice,
    // evaluation,factory} and src/api, so it remains fully linted.
    'src/lib/api.ts',
    'src/lib/v3Api.ts',
    'src/lib/mock.ts',
    'src/lib/types.ts',
    'src/lib/types.v2.2.2.ts',
    'src/lib/adapters.v2.2.2.ts',
    'src/pages/AgentWorkbench.tsx',
    'src/pages/AuditPanel.tsx',
    'src/pages/Dashboard.tsx',
    'src/pages/DeliveryEvidence.tsx',
    'src/pages/ErrorFeedback.tsx',
    'src/pages/FalsePremiseTraining.tsx',
    'src/pages/ModelEvaluation.tsx',
    'src/pages/ModelEvaluation.v2.2.2.tsx',
    'src/pages/ModelHub.tsx',
    'src/pages/Overview.tsx',
    'src/pages/Overview.v2.2.2.tsx',
    'src/pages/PatientCard.tsx',
    'src/pages/PhysicianProfile.tsx',
    'src/pages/PracticeWorkspace.tsx',
    'src/pages/PracticeWorkspace.v2.2.2.tsx',
    'src/pages/QuestionBanks.tsx',
    'src/pages/QuestionBanks.v2.2.2.tsx',
    'src/pages/ReportDraft.tsx',
    'src/pages/SkillsCenter.tsx',
    'src/pages/StudyCenter.tsx',
    'src/pages/TrainingCenter.tsx',
    'src/components/ErrorBoundary.tsx',
    'src/components/Primitives.tsx',
    'src/components/ProviderPreflightPanel.tsx',
  ]),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
  },
])
