import React from 'react';
import { AnyEvent } from '@/types/events';
import { LogEventComponent } from './LogEventComponent';
import { CostEventComponent } from './CostEventComponent';
import { ExecutionEventComponent } from './ExecutionEventComponent';
import { OutputEventComponent } from './OutputEventComponent';
import { ValidationEventComponent } from './ValidationEventComponent';
import { ExecutionSummaryEventComponent } from './ExecutionSummaryEventComponent';
import { 
  TestStartedEventComponent, 
  TestScenarioCompletedEventComponent, 
  TestCompletedEventComponent 
} from './TestEventComponent';
import { 
  EvaluationStartedEventComponent, 
  EvaluationProgressEventComponent, 
  EvaluationCompletedEventComponent 
} from './EvaluationEventComponent';

interface EventRendererProps {
  event: AnyEvent;
}

export const EventRenderer: React.FC<EventRendererProps> = ({ event }) => {
  switch (event.event_type) {
    case 'log':
      return <LogEventComponent event={event} />;
    case 'cost':
      return <CostEventComponent event={event} />;
    case 'execution':
      return <ExecutionEventComponent event={event} />;
    case 'execution_summary':
      return <ExecutionSummaryEventComponent event={event} />;
    case 'output':
      return <OutputEventComponent event={event} />;
    case 'validation':
      return <ValidationEventComponent event={event} />;
    case 'test_started':
      return <TestStartedEventComponent event={event} />;
    case 'test_scenario_completed':
      return <TestScenarioCompletedEventComponent event={event} />;
    case 'test_completed':
      return <TestCompletedEventComponent event={event} />;
    case 'evaluation_started':
      return <EvaluationStartedEventComponent event={event} />;
    case 'evaluation_progress':
      return <EvaluationProgressEventComponent event={event} />;
    case 'evaluation_completed':
      return <EvaluationCompletedEventComponent event={event} />;
    default:
      return (
        <div className="py-2 px-3 text-sm text-muted-foreground border-b border-border/50">
          Unknown event type: {JSON.stringify(event)}
        </div>
      );
  }
};



