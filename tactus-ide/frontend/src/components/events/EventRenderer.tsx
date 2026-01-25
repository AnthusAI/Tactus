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
import { ToolCallEventComponent } from './ToolCallEventComponent';
import { CheckpointEventComponent } from './CheckpointEventComponent';
import { ContainerStatusEventComponent } from './ContainerStatusEventComponent';
import { HITLEventComponent } from './HITLEventComponent';
import { BaseEventComponent } from './BaseEventComponent';

interface EventRendererProps {
  event: AnyEvent;
  isAlternate?: boolean;
  onJumpToSource?: (filePath: string, lineNumber: number) => void;
  onHITLRespond?: (requestId: string, value: any) => void;
}

export const EventRenderer: React.FC<EventRendererProps> = ({ event, isAlternate, onJumpToSource, onHITLRespond }) => {
  // Agent turn events are now converted to loading events in useEventStream
  // so they won't reach here anymore

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
    case 'tool_call':
      return <ToolCallEventComponent event={event} isAlternate={isAlternate} />;
    case 'checkpoint_created':
      return <CheckpointEventComponent event={event} isAlternate={isAlternate} onJumpToSource={onJumpToSource} />;
    case 'container_status':
      return <ContainerStatusEventComponent event={event as any} isAlternate={isAlternate} />;
    case 'hitl.request':
      return <HITLEventComponent event={event} isAlternate={isAlternate} onRespond={onHITLRespond} />;
    case 'hitl.cancel':
      // Cancel events are informational only - the UI clears the pending request
      return (
        <BaseEventComponent isAlternate={isAlternate} className="py-2 px-3 text-sm text-muted-foreground">
          HITL request {(event as any).request_id} cancelled: {(event as any).reason}
        </BaseEventComponent>
      );
    default:
      return (
        <BaseEventComponent isAlternate={isAlternate} className="py-2 px-3 text-sm text-muted-foreground">
          Unknown event type: {JSON.stringify(event)}
        </BaseEventComponent>
      );
  }
};





