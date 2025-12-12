/**
 * Event type definitions for IDE structured output.
 * 
 * These match the Pydantic models in tactus-ide/backend/events.py
 */

export interface BaseEvent {
  event_type: string;
  timestamp: string;
  procedure_id?: string;
}

export interface LogEvent extends BaseEvent {
  event_type: 'log';
  level: string;
  message: string;
  context?: Record<string, any>;
  logger_name?: string;
}

export interface ExecutionEvent extends BaseEvent {
  event_type: 'execution';
  lifecycle_stage: 'start' | 'complete' | 'error' | 'waiting';
  details?: Record<string, any>;
  exit_code?: number;
}

export interface OutputEvent extends BaseEvent {
  event_type: 'output';
  stream: 'stdout' | 'stderr';
  content: string;
}

export interface ValidationEvent extends BaseEvent {
  event_type: 'validation';
  valid: boolean;
  errors: Array<{
    message: string;
    line?: number;
    column?: number;
    severity: string;
  }>;
}

export interface ExecutionSummaryEvent extends BaseEvent {
  event_type: 'execution_summary';
  result: any;
  final_state: Record<string, any>;
  iterations: number;
  tools_used: string[];
}

export type AnyEvent = LogEvent | ExecutionEvent | OutputEvent | ValidationEvent | ExecutionSummaryEvent;


