import { describe, expect, it } from 'vitest'

import { displayCatalogModels, displayModelName, resolveModelName } from '../pages/evaluation/evaluationDisplay'

describe('evaluation model display names', () => {
  it('shows the readable final segment while retaining a unique full id for requests', () => {
    const fullModel = '@cf/qwen/qwen3-30b-a3b-fp8'
    expect(displayModelName(fullModel)).toBe('qwen3-30b-a3b-fp8')
    expect(displayCatalogModels([fullModel])).toEqual(['qwen3-30b-a3b-fp8'])
    expect(resolveModelName('qwen3-30b-a3b-fp8', [fullModel])).toBe(fullModel)
  })

  it('keeps the full id when short names collide', () => {
    const models = ['provider-a/shared-model', 'provider-b/shared-model']
    expect(displayCatalogModels(models)).toEqual(models)
    expect(resolveModelName('shared-model', models)).toBe('shared-model')
  })
})
