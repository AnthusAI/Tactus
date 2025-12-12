import React from 'react';
import { AnyEvent } from '@/types/events';
import { LogEventComponent } from './LogEventComponent';
import { ExecutionEventComponent } from './ExecutionEventComponent';
import { OutputEventComponent } from './OutputEventComponent';
import { ValidationEventComponent } from './ValidationEventComponent';
import { ExecutionSummaryEventComponent } from './ExecutionSummaryEventComponent';

interface EventRendererProps {
  event: AnyEvent;
}

export const EventRenderer: React.FC<EventRendererProps> = ({ event }) => {
  switch (event.event_type) {
    case 'log':
      return <LogEventComponent event={event} />;
    case 'execution':
      return <ExecutionEventComponent event={event} />;
    case 'execution_summary':
      return <ExecutionSummaryEventComponent event={event} />;
    case 'output':
      return <OutputEventComponent event={event} />;
    case 'validation':
      return <ValidationEventComponent event={event} />;
    default:
      return (
        <div className="py-2 px-3 text-sm text-muted-foreground border-b border-border/50">
          Unknown event type: {JSON.stringify(event)}
        </div>
      );
  }
};


