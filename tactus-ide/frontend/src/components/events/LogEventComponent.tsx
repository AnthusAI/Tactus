import React, { useState } from 'react';
import { LogEvent } from '@/types/events';
import { ChevronDown, ChevronRight, Bug, Info, AlertTriangle, AlertCircle, Siren } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BaseEventComponent } from './BaseEventComponent';
import { Timestamp } from '../Timestamp';

interface LogEventComponentProps {
  event: LogEvent;
  isAlternate?: boolean;
}

const levelConfig = {
  DEBUG: {
    icon: Bug,
    color: 'text-muted-foreground',
  },
  INFO: {
    icon: Info,
    color: 'text-muted-foreground',
  },
  WARNING: {
    icon: AlertTriangle,
    color: 'text-yellow-500',
  },
  ERROR: {
    icon: AlertCircle,
    color: 'text-red-500',
    bg: 'bg-red-500/10',
  },
  CRITICAL: {
    icon: Siren,
    color: 'text-red-700',
    bg: 'bg-red-700/10',
  },
};

export const LogEventComponent: React.FC<LogEventComponentProps> = ({ event, isAlternate }) => {
  // Auto-expand context for "Agent completed" messages
  const autoExpand = event.message.includes('Agent completed');
  const [contextExpanded, setContextExpanded] = useState(autoExpand);
  const hasContext = event.context && Object.keys(event.context).length > 0;

  const config = levelConfig[event.level as keyof typeof levelConfig] || levelConfig.INFO;
  const Icon = config.icon;

  return (
    <BaseEventComponent isAlternate={isAlternate} className={cn('py-2 px-3 text-sm', config.bg)}>
      <div className="flex items-start gap-2">
        <Icon className={cn('h-5 w-5 flex-shrink-0 stroke-[2]', config.color)} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <div className="text-foreground">{event.message}</div>
            <Timestamp timestamp={event.timestamp} className="whitespace-nowrap" />
          </div>
          {hasContext && !autoExpand && (
            <button
              onClick={() => setContextExpanded(!contextExpanded)}
              className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mt-1"
            >
              {contextExpanded ? <ChevronDown className="h-3 w-3 stroke-[2]" /> : <ChevronRight className="h-3 w-3 stroke-[2]" />}
              Context
            </button>
          )}
        </div>
      </div>
      {hasContext && (autoExpand || contextExpanded) && (
        <div className="mt-2 ml-7 bg-background rounded p-3 border">
          <pre className="text-xs font-mono whitespace-pre-wrap">{JSON.stringify(event.context, null, 2)}</pre>
        </div>
      )}
    </BaseEventComponent>
  );
};





