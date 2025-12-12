import React from 'react';
import { ValidationEvent } from '@/types/events';
import { CheckCircle, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ValidationEventComponentProps {
  event: ValidationEvent;
}

export const ValidationEventComponent: React.FC<ValidationEventComponentProps> = ({ event }) => {
  return (
    <div className={cn('py-3 px-3 border-b border-border', event.valid ? 'bg-green-500/10' : 'bg-red-500/10')}>
      <div className="flex items-center gap-2">
        {event.valid ? (
          <CheckCircle className="h-4 w-4 text-green-500" />
        ) : (
          <XCircle className="h-4 w-4 text-red-500" />
        )}
        <span className={cn('font-semibold', event.valid ? 'text-green-500' : 'text-red-500')}>
          Validation {event.valid ? 'Passed' : 'Failed'}
        </span>
        <span className="ml-auto text-xs text-muted-foreground">
          {new Date(event.timestamp).toLocaleTimeString()}
        </span>
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
  );
};



