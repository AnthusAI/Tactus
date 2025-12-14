import React from 'react';
import { AnyEvent } from '@/types/events';
import { LogEventComponent } from './LogEventComponent';
import { CostEventComponent } from './CostEventComponent';
import { ExecutionEventComponent } from './ExecutionEventComponent';
import { OutputEventComponent } from './OutputEventComponent';
import { ValidationEventComponent } from './ValidationEventComponent';
import { ExecutionSummaryEventComponent } from './ExecutionSummaryEventComponent';
import { LoadingEventComponent } from './LoadingEventComponent';
import { AgentStreamingComponent } from './AgentStreamingComponent';
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
import { BaseEventComponent } from './BaseEventComponent';

interface EventRendererProps {
  event: AnyEvent;
  isAlternate?: boolean;
}

export const EventRenderer: React.FC<EventRendererProps> = ({ event, isAlternate }) => {
  // Convert AgentTurnEvent to LoadingEvent for display
  if (event.event_type === 'agent_turn') {
    const agentEvent = event as any;
    if (agentEvent.stage === 'started') {
      // Show as loading indicator
      const loadingEvent = {
        event_type: 'loading',
        message: `Waiting for ${agentEvent.agent_name} response...`,
        timestamp: agentEvent.timestamp,
        procedure_id: agentEvent.procedure_id,
      };
      return <LoadingEventComponent event={loadingEvent as any} isAlternate={isAlternate} />;
    } else if (agentEvent.stage === 'completed') {
      // Show as a log event: "Agent {name} completed"
      const logEvent = {
        event_type: 'log',
        level: 'INFO',
        message: `Agent ${agentEvent.agent_name} completed`,
        context: null,
        timestamp: agentEvent.timestamp,
        procedure_id: agentEvent.procedure_id,
      };
      return <LogEventComponent event={logEvent as any} isAlternate={isAlternate} />;
    }
  }
  
  switch (event.event_type) {
    case 'log':
      return <LogEventComponent event={event} isAlternate={isAlternate} />;
    case 'cost':
      return <CostEventComponent event={event} isAlternate={isAlternate} />;
    case 'agent_stream_chunk':
      return <AgentStreamingComponent event={event} isAlternate={isAlternate} />;
    case 'execution':
      // Filter out "Completed" message (lifecycle_stage: 'complete')
      // Exit code is now shown in ExecutionSummaryEvent
      const execEvent = event as any;
      if (execEvent.lifecycle_stage === 'complete') {
        return null;
      }
      return <ExecutionEventComponent event={event} isAlternate={isAlternate} />;
    case 'execution_summary':
      return <ExecutionSummaryEventComponent event={event} isAlternate={isAlternate} />;
    case 'output':
      return <OutputEventComponent event={event} isAlternate={isAlternate} />;
    case 'validation':
      return <ValidationEventComponent event={event} isAlternate={isAlternate} />;
    case 'loading':
      return <LoadingEventComponent event={event} isAlternate={isAlternate} />;
    case 'test_started':
      return <TestStartedEventComponent event={event} isAlternate={isAlternate} />;
    case 'test_scenario_completed':
      return <TestScenarioCompletedEventComponent event={event} isAlternate={isAlternate} />;
    case 'test_completed':
      return <TestCompletedEventComponent event={event} isAlternate={isAlternate} />;
    case 'evaluation_started':
      return <EvaluationStartedEventComponent event={event} isAlternate={isAlternate} />;
    case 'evaluation_progress':
      return <EvaluationProgressEventComponent event={event} isAlternate={isAlternate} />;
    case 'evaluation_completed':
      return <EvaluationCompletedEventComponent event={event} isAlternate={isAlternate} />;
    default:
      return (
        <BaseEventComponent isAlternate={isAlternate} className="py-2 px-3 text-sm text-muted-foreground">
          Unknown event type: {JSON.stringify(event)}
        </BaseEventComponent>
      );
  }
};





