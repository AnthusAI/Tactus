import React from 'react';
import { Loader2 } from 'lucide-react';
import { BaseEventComponent } from './BaseEventComponent';
import { LoadingEvent } from '@/types/events';
import { Duration } from '../Duration';

interface LoadingEventComponentProps {
  event: LoadingEvent;
  isAlternate?: boolean;
}

export const LoadingEventComponent: React.FC<LoadingEventComponentProps> = ({ 
  event,
  isAlternate
}) => {
  return (
    <BaseEventComponent isAlternate={isAlternate} className="py-2 px-3 text-sm">
      <div className="flex items-start gap-2">
        <Loader2 className="h-5 w-5 text-muted-foreground animate-spin flex-shrink-0 stroke-[2.5]" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className="text-foreground">{event.message}</span>
            {event.timestamp && <Duration startTime={event.timestamp} />}
          </div>
        </div>
      </div>
    </BaseEventComponent>
  );
};
