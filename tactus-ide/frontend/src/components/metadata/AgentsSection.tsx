import React from 'react';
import { AgentDeclaration } from '@/types/metadata';
import { Bot, Wrench } from 'lucide-react';

interface AgentsSectionProps {
  agents: Record<string, AgentDeclaration>;
}

export const AgentsSection: React.FC<AgentsSectionProps> = ({ agents }) => {
  const agentList = Object.values(agents);

  if (agentList.length === 0) {
    return null;
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Bot className="h-4 w-4" />
        <h3 className="font-semibold text-sm">Agents</h3>
      </div>
      <div className="space-y-3">
        {agentList.map((agent) => (
          <div key={agent.name} className="pl-4 border-l-2 border-muted">
            <code className="text-sm font-mono font-semibold">{agent.name}</code>
            <div className="mt-0.5">
              <div className="text-xs text-muted-foreground leading-tight">
                {agent.model}
              </div>
              <div className="text-xs text-muted-foreground leading-tight">
                {agent.provider}
              </div>
            </div>
            {agent.system_prompt && agent.system_prompt !== '[Dynamic Prompt]' && (
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                {agent.system_prompt}
              </p>
            )}
            {agent.system_prompt === '[Dynamic Prompt]' && (
              <p className="text-xs text-muted-foreground italic mt-1">
                Dynamic system prompt
              </p>
            )}
            {agent.tools.length > 0 && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground mt-1">
                <Wrench className="h-3 w-3" />
                <span>{agent.tools.length} tool{agent.tools.length !== 1 ? 's' : ''}</span>
                <span className="text-xs">({agent.tools.slice(0, 3).join(', ')}{agent.tools.length > 3 ? '...' : ''})</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
