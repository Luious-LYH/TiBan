import { useQuery } from '@tanstack/react-query'

import { getInstanceSettings } from '../../api/client'

export function useAgentAvailability(enabled = true) {
  const query = useQuery({
    queryKey: ['instance-settings'],
    queryFn: getInstanceSettings,
    enabled,
    retry: false,
    staleTime: 30_000,
  })

  return { ...query, agentAvailable: query.data?.llm.agent_available === true }
}
