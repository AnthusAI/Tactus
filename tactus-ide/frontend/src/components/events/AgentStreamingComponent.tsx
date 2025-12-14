import React from 'react';
import { AgentStreamChunkEvent } from '@/types/events';
import { Bot } from 'lucide-react';
import { BaseEventComponent } from './BaseEventComponent';
import { Timestamp } from '../Timestamp';

interface AgentStreamingComponentProps {
  event: AgentStreamChunkEvent;
  isAlternate?: boolean;
}

export const AgentStreamingComponent: React.FC<AgentStreamingComponentProps> = ({ event, isAlternate }) => {
  return (
    <BaseEventComponent isAlternate={isAlternate} className="py-2 px-3 text-sm">
      <div className="flex items-start gap-2">
        <Bot className="h-5 w-5 text-muted-foreground flex-shrink-0 stroke-[2]" />
        <div className="flex-1 min-w-0">
          {/* Agent name and timestamp - clean alignment */}
          <div className="flex items-center justify-between">
            <span className="text-foreground">{event.agent_name}</span>
            <Timestamp timestamp={event.timestamp} />
          </div>
        </div>
      </div>
      
      {/* Streaming response text */}
      <div className="mt-2 ml-7 bg-background rounded p-3 border">
        <pre className="text-xs font-mono whitespace-pre-wrap">
          {event.accumulated_text}
        </pre>
      </div>
      
      {/* Streaming indicator */}
      <div className="mt-2 ml-7 text-xs text-muted-foreground">
        Streaming...
      </div>
    </BaseEventComponent>
  );
};
