import { useEffect, useState } from 'react'
import { PlayCircle, Sparkles } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockSkills } from '../lib/mock'
import type { SkillDefinition } from '../lib/types'

const toneByRisk = {
  low: 'green',
  medium: 'amber',
  high: 'red',
} as const

export function SkillsCenter() {
  const [skills, setSkills] = useState<SkillDefinition[]>(mockSkills)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [running, setRunning] = useState('')

  useEffect(() => {
    api.skills().then((items) => setSkills(items))
  }, [])

  const runSkill = async (id: string) => {
    setRunning(id)
    setResult(await api.runSkill(id))
    setRunning('')
  }

  return (
    <div className="page-stack">
      <Card className="focus-band">
        <div>
          <span className="eyebrow">Controlled skills</span>
          <h2>Skills 中心</h2>
          <p>平台将 Agent 能力拆成可审计、可禁用、可加安全等级的技能，而不是自由聊天机器人。</p>
        </div>
        <Sparkles size={42} />
      </Card>
      <div className="skills-grid">
        {skills.map((skill) => (
          <Card key={skill.id}>
            <SectionTitle eyebrow={skill.category} title={skill.name} action={<Tag tone={toneByRisk[skill.risk_level]}>{skill.risk_level}</Tag>} />
            <p className="muted">{skill.description}</p>
            <button className="button secondary" type="button" onClick={() => runSkill(skill.id)} disabled={running === skill.id || !skill.enabled}>
              <PlayCircle size={16} /> 运行 skill
            </button>
          </Card>
        ))}
      </div>
      {result ? (
        <Card>
          <SectionTitle eyebrow="Skill result" title="最近一次调用结果" />
          <pre className="json-view">{JSON.stringify(result, null, 2)}</pre>
        </Card>
      ) : null}
    </div>
  )
}

