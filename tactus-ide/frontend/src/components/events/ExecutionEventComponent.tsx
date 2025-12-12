import React from 'react';
import { ExecutionEvent } from '@/types/events';
import { Play, CheckCircle, XCircle, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ExecutionEventComponentProps {
  event: ExecutionEvent;
}

const stageConfig = {
  start: {
    icon: Play,
    label: 'Started',
    color: 'text-blue-500',
    bg: 'bg-blue-500/10',
  },
  complete: {
    icon: CheckCircle,
    label: 'Completed',
    color: 'text-green-500',
    bg: 'bg-green-500/10',
  },
  error: {
    icon: XCircle,
    label: 'Failed',
    color: 'text-red-500',
    bg: 'bg-red-500/10',
  },
  waiting: {
    icon: Clock,
    label: 'Waiting',
    color: 'text-yellow-500',
    bg: 'bg-yellow-500/10',
  },
};

export const ExecutionEventComponent: React.FC<ExecutionEventComponentProps> = ({ event }) => {
  const config = stageConfig[event.lifecycle_stage as keyof typeof stageConfig] || stageConfig.start;
  const Icon = config.icon;

  return (
    <div className={cn('py-3 px-3 border-b border-border', config.bg)}>
      <div className="flex items-center gap-2">
        <Icon className={cn('h-4 w-4', config.color)} />
        <span className={cn('font-semibold', config.color)}>{config.label}</span>
        {event.exit_code !== undefined && (
          <span className="text-xs text-muted-foreground">
            (exit code: {event.exit_code})
          </span>
        )}
        <span className="ml-auto text-xs text-muted-foreground">
          {new Date(event.timestamp).toLocaleTimeString()}
        </span>
      </div>
      {event.details && Object.keys(event.details).length > 0 && (
        <div className="mt-1 text-xs text-muted-foreground">
          {event.details.path && <div>Path: {event.details.path}</div>}
          {event.details.error && <div className="text-red-500">Error: {event.details.error}</div>}
        </div>
      )}
    </div>
  );
};



