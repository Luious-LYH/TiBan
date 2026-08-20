const apiBase = process.env.ARIS_API_BASE || 'http://127.0.0.1:8001/api'

const endpoints = [
  '/health',
  '/session',
  '/models/evaluation',
  '/practice/state',
  '/practice/questions',
  '/dashboard',
  '/platform/readiness',
  '/platform/delivery-report',
  '/models',
  '/knowledge/real-samples',
  '/skills',
  '/audit',
]

const banned = [
  'Kvasir',
  'EndoBench',
  'HyperKvasir',
  '智能服务',
  'fallback',
  'api_source',
  'key_persisted',
  'backend live',
  'frontend fallback',
  '交付证据',
  '台账',
  'Skills',
  '训练模型',
  '研修对照',
  '研修对照',
  '原子事实',
  '原子证据',
  '原子查询',
  '原子错因',
  '医生审核',
  '学员',
  '评审',
  'ARIS v2',
  'v2.0',
  '提示词',
  '包装',
  '竞赛',
]

const failures = []
let dynamicQuestionEndpoint = null

try {
  const response = await fetch(`${apiBase.replace(/\/$/, '')}/practice/questions?limit=1`)
  const payload = await response.json()
  const firstId = payload?.items?.[0]?.id
  if (firstId) dynamicQuestionEndpoint = `/practice/questions/${encodeURIComponent(firstId)}`
} catch (error) {
  failures.push({
    endpoint: '/practice/questions?limit=1',
    error: error instanceof Error ? error.message : String(error),
  })
}

if (dynamicQuestionEndpoint) endpoints.splice(5, 0, dynamicQuestionEndpoint)

for (const endpoint of endpoints) {
  const url = `${apiBase.replace(/\/$/, '')}${endpoint}`
  try {
    const response = await fetch(url)
    const text = await response.text()
    if (!response.ok) {
      failures.push({ endpoint, status: response.status, snippet: text.slice(0, 240) })
      continue
    }
    const hits = banned.filter((word) => text.includes(word))
    if (hits.length) {
      failures.push({ endpoint, hits, snippet: text.slice(0, 600) })
    }
  } catch (error) {
    failures.push({ endpoint, error: error instanceof Error ? error.message : String(error) })
  }
}

console.log(JSON.stringify({ apiBase, checked: endpoints.length, failures }, null, 2))
process.exitCode = failures.length ? 2 : 0

