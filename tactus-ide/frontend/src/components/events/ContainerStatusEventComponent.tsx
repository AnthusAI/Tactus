import React from 'react';
import { Box, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { BaseEventComponent } from './BaseEventComponent';
import { Duration } from '../Duration';

interface ContainerStatusEvent {
  event_type: 'container_status';
  status: 'starting' | 'started' | 'running' | 'stopped' | 'error';
  execution_id: string;
  timestamp: string;
  error?: string;
  completed?: boolean;
  duration_ms?: number;
}

interface ContainerStatusEventComponentProps {
  event: ContainerStatusEvent;
  isAlternate?: boolean;
}

export const ContainerStatusEventComponent: React.FC<ContainerStatusEventComponentProps> = ({
  event,
  isAlternate
}) => {
  const getStatusDisplay = () => {
    switch (event.status) {
      case 'starting':
        return {
          icon: <Loader2 className="h-5 w-5 text-blue-500 animate-spin flex-shrink-0 stroke-[2.5]" />,
          message: 'Starting container...',
          textClass: 'text-foreground',
          showLiveDuration: true,
        };
      case 'started':
        return {
          icon: <Box className="h-5 w-5 text-muted-foreground flex-shrink-0 stroke-[2.5]" />,
          message: 'Container started',
          textClass: 'text-foreground',
          showLiveDuration: false,
        };
      case 'running':
        return {
          icon: <Box className="h-5 w-5 text-green-600 flex-shrink-0 stroke-[2.5]" />,
          message: 'Container running',
          textClass: 'text-foreground',
          showLiveDuration: false,
        };
      case 'stopped':
        return {
          icon: <CheckCircle2 className="h-5 w-5 text-muted-foreground flex-shrink-0 stroke-[2.5]" />,
          message: 'Container stopped',
          textClass: 'text-muted-foreground',
          showLiveDuration: false,
        };
      case 'error':
        return {
          icon: <XCircle className="h-5 w-5 text-red-500 flex-shrink-0 stroke-[2.5]" />,
          message: event.error || 'Container error',
          textClass: 'text-red-600',
          showLiveDuration: false,
        };
      default:
        return {
          icon: <Box className="h-5 w-5 text-muted-foreground flex-shrink-0 stroke-[2.5]" />,
          message: `Container: ${event.status}`,
          textClass: 'text-muted-foreground',
          showLiveDuration: false,
        };
    }
  };

  const { icon, message, textClass, showLiveDuration } = getStatusDisplay();
  const isCompleted = event.completed;
  const durationMs = event.duration_ms;

  return (
    <BaseEventComponent isAlternate={isAlternate} className="py-2 px-3 text-sm">
      <div className="flex items-start gap-2">
        {icon}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className={textClass}>{message}</span>
            {isCompleted && durationMs !== undefined ? (
              <span className="text-xs text-muted-foreground">
                {(durationMs / 1000).toFixed(2)}s
              </span>
            ) : (
              showLiveDuration && event.timestamp && <Duration startTime={event.timestamp} />
            )}
          </div>
        </div>
      </div>
    </BaseEventComponent>
  );
};
