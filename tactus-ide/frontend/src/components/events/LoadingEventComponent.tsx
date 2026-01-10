import React from 'react';
import { Loader2, CheckCircle2 } from 'lucide-react';
import { BaseEventComponent } from './BaseEventComponent';
import { LoadingEvent } from '@/types/events';
import { Duration } from '../Duration';

interface LoadingEventComponentProps {
  event: LoadingEvent & { completed?: boolean; duration_ms?: number };
  isAlternate?: boolean;
}

export const LoadingEventComponent: React.FC<LoadingEventComponentProps> = ({
  event,
  isAlternate
}) => {
  const isCompleted = event.completed;
  const durationMs = event.duration_ms;

  return (
    <BaseEventComponent isAlternate={isAlternate} className="py-2 px-3 text-sm">
      <div className="flex items-start gap-2">
        {isCompleted ? (
          <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0 stroke-[2.5]" />
        ) : (
          <Loader2 className="h-5 w-5 text-muted-foreground animate-spin flex-shrink-0 stroke-[2.5]" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className="text-foreground">{event.message}</span>
            {isCompleted && durationMs !== undefined ? (
              <span className="text-xs text-muted-foreground">
                {(durationMs / 1000).toFixed(2)}s
              </span>
            ) : (
              event.timestamp && <Duration startTime={event.timestamp} />
            )}
          </div>
        </div>
      </div>
    </BaseEventComponent>
  );
};
