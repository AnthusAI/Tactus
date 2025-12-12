import React from 'react';
import { OutputEvent } from '@/types/events';
import { cn } from '@/lib/utils';

interface OutputEventComponentProps {
  event: OutputEvent;
}

export const OutputEventComponent: React.FC<OutputEventComponentProps> = ({ event }) => {
  const isStderr = event.stream === 'stderr';

  return (
    <div className={cn('py-1 px-3 font-mono text-xs border-b border-border/30', isStderr && 'text-red-400')}>
      <pre className="whitespace-pre-wrap break-words">{event.content}</pre>
    </div>
  );
};



