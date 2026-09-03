import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getInstanceSettings } from '../api/client'
import { SettingsPage } from '../pages/settings/SettingsPage'

vi.mock('../api/client', () => ({
  applyInstanceEmbedding: vi.fn(),
  applyInstanceLLM: vi.fn(),
  getInstanceSettings: vi.fn(),
  rebuildInstanceIndexes: vi.fn(),
  restoreInstanceEmbedding: vi.fn(),
  restoreInstanceLLM: vi.fn(),
  testInstanceEmbedding: vi.fn(),
  testInstanceLLM: vi.fn(),
}))

const mockedGetInstanceSettings = vi.mocked(getInstanceSettings)

const baseSettings = {
  llm: {
    provider: 'cloudflare_workers_ai',
    base_url_configured: true,
    api_key_configured: true,
    agent_available: true,
    agent_mode: 'provider',
    model: '@cf/qwen/qwen3-30b-a3b-fp8',
    reasoning_effort: null,
    runtime_override: false,
    restores_default_on_restart: true,
    private_network_allowed: false,
  },
  embedding: {
    mode: 'api',
    provider: 'siliconflow',
    base_url_configured: true,
    api_key_configured: true,
    model: 'BAAI/bge-m3',
    local_model: 'BAAI/bge-small-zh-v1.5',
    active_provider: 'siliconflow',
    active_model: 'BAAI/bge-m3',
    reranker_mode: 'api',
    reranker_provider: 'siliconflow',
    reranker_model: 'BAAI/bge-reranker-v2-m3',
    batch_size: 32,
    runtime_override: false,
    restores_default_on_restart: true,
    model_switch_supported: true,
    knowledge_index_status: 'ready',
    memory_index_status: 'ready',
  },
  api_source: 'backend',
}

function renderSettings() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}><SettingsPage /></QueryClientProvider>)
}

describe('SettingsPage default configuration actions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedGetInstanceSettings.mockResolvedValue(baseSettings)
  })

  it('disables default and restore actions when both capabilities already use project defaults', async () => {
    renderSettings()

    expect(await screen.findByTestId('settings-page')).toBeInTheDocument()
    for (const button of screen.getAllByRole('button', { name: /^使用项目默认$/ })) expect(button).toBeDisabled()
    expect(screen.getByRole('button', { name: /^恢复默认$/ })).toBeDisabled()
  })

  it('enables switching back to defaults after a runtime override is active', async () => {
    mockedGetInstanceSettings.mockResolvedValue({
      ...baseSettings,
      llm: { ...baseSettings.llm, runtime_override: true },
      embedding: { ...baseSettings.embedding, runtime_override: true },
    })
    renderSettings()

    expect(await screen.findByTestId('settings-page')).toBeInTheDocument()
    const user = userEvent.setup()
    const defaultChoiceButtons = screen.getAllByRole('button', { name: /^项目默认$/ })
    await user.click(defaultChoiceButtons[0])
    await user.click(defaultChoiceButtons[1])

    for (const button of screen.getAllByRole('button', { name: /^使用项目默认$/ })) expect(button).toBeEnabled()
    expect(screen.getByRole('button', { name: /^恢复默认$/ })).toBeEnabled()
  })

  it('clearly gates Agent use when the active provider is not available', async () => {
    mockedGetInstanceSettings.mockResolvedValue({
      ...baseSettings,
      llm: { ...baseSettings.llm, api_key_configured: false, agent_available: false, agent_mode: 'rule' },
    })
    renderSettings()

    expect(await screen.findByText('需要配置 API 才能使用 Agent')).toBeInTheDocument()
    expect(screen.getByText(/题库、刷题和复习仍可使用/)).toBeInTheDocument()
  })
})
