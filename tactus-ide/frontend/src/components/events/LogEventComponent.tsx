import React, { useState } from 'react';
import { LogEvent } from '@/types/events';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface LogEventComponentProps {
  event: LogEvent;
}

const levelColors = {
  DEBUG: 'text-gray-500',
  INFO: 'text-blue-500',
  WARNING: 'text-yellow-500',
  ERROR: 'text-red-500',
  CRITICAL: 'text-red-700',
};

const levelBgColors = {
  DEBUG: 'bg-gray-500/10',
  INFO: 'bg-blue-500/10',
  WARNING: 'bg-yellow-500/10',
  ERROR: 'bg-red-500/10',
  CRITICAL: 'bg-red-700/10',
};

export const LogEventComponent: React.FC<LogEventComponentProps> = ({ event }) => {
  const [contextExpanded, setContextExpanded] = useState(false);
  const hasContext = event.context && Object.keys(event.context).length > 0;

  const levelColor = levelColors[event.level as keyof typeof levelColors] || 'text-gray-500';
  const levelBg = levelBgColors[event.level as keyof typeof levelBgColors] || 'bg-gray-500/10';

  return (
    <div className="py-2 px-3 text-sm border-b border-border/50">
      <div className="flex items-start gap-2">
        <span className={cn('text-xs font-mono px-1.5 py-0.5 rounded', levelBg, levelColor)}>
          {event.level}
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-foreground">{event.message}</div>
          {hasContext && (
            <button
              onClick={() => setContextExpanded(!contextExpanded)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mt-1"
            >
              {contextExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Context
            </button>
          )}
          {contextExpanded && hasContext && (
            <pre className="mt-2 text-xs bg-muted/30 p-2 rounded overflow-x-auto">
              {JSON.stringify(event.context, null, 2)}
            </pre>
          )}
        </div>
        <span className="text-xs text-muted-foreground whitespace-nowrap">
          {new Date(event.timestamp).toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
};



