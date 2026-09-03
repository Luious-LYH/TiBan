export function displayModelName(value: string) {
  const normalized = value.trim().replace(/\/+$/, '')
  return normalized.split('/').pop() || normalized
}

export function displayCatalogModels(models: string[]) {
  const names = models.map(displayModelName)
  const counts = new Map<string, number>()
  names.forEach((name) => counts.set(name, (counts.get(name) ?? 0) + 1))
  return models.map((model, index) => counts.get(names[index]) === 1 ? names[index] : model)
}

export function resolveModelName(value: string, catalogModels: string[]) {
  const normalized = value.trim()
  const exact = catalogModels.find((model) => model === normalized)
  if (exact) return exact
  const matches = catalogModels.filter((model) => displayModelName(model) === normalized)
  return matches.length === 1 ? matches[0] : normalized
}
