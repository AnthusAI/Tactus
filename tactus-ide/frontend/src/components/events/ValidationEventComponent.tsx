import React from 'react';
import { ValidationEvent } from '@/types/events';
import { CheckCircle, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BaseEventComponent } from './BaseEventComponent';
import { Timestamp } from '../Timestamp';

interface ValidationEventComponentProps {
  event: ValidationEvent;
  isAlternate?: boolean;
}

export const ValidationEventComponent: React.FC<ValidationEventComponentProps> = ({ event, isAlternate }) => {
  return (
    <BaseEventComponent isAlternate={isAlternate} className={cn('py-3 px-3 text-sm', event.valid ? 'bg-green-500/10' : 'bg-red-500/10')}>
      <div className="flex items-start gap-2">
        {event.valid ? (
          <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0 stroke-[2]" />
        ) : (
          <XCircle className="h-5 w-5 text-red-500 flex-shrink-0 stroke-[2]" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className={event.valid ? 'text-green-500' : 'text-red-500'}>
              Validation {event.valid ? 'Passed' : 'Failed'}
            </span>
            <Timestamp timestamp={event.timestamp} />
          </div>
          {event.errors.length > 0 && (
            <div className="mt-2 space-y-1">
              {event.errors.map((err, i) => (
                <div key={i} className="text-sm text-red-600">
                  {err.line && <span className="font-mono text-xs mr-2">Line {err.line}:</span>}
                  {err.message}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </BaseEventComponent>
  );
};





