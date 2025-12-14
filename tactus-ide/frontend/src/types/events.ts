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

export interface CostEvent extends BaseEvent {
  event_type: 'cost';
  
  // Agent/Model Info
  agent_name: string;
  model: string;
  provider: string;
  
  // Token Usage (Primary)
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  
  // Cost (Primary)
  prompt_cost: number;
  completion_cost: number;
  total_cost: number;
  
  // Performance (Details)
  duration_ms?: number;
  latency_ms?: number;
  
  // Retry/Validation (Details)
  retry_count: number;
  validation_errors: string[];
  
  // Cache (Details)
  cache_hit: boolean;
  cache_tokens?: number;
  cache_cost?: number;
  
  // Messages (Details)
  message_count: number;
  new_message_count: number;
  
  // Request Metadata (Details)
  request_id?: string;
  model_version?: string;
  temperature?: number;
  max_tokens?: number;
  
  // Raw tracing data
  raw_tracing_data?: Record<string, any>;
  
  // Response data
  response_data?: Record<string, any>;
}

export interface ExecutionSummaryEvent extends BaseEvent {
  event_type: 'execution_summary';
  result: any;
  final_state: Record<string, any>;
  iterations: number;
  tools_used: string[];
  
  // Cost tracking
  total_cost: number;
  total_tokens: number;
  cost_breakdown: CostEvent[];
  
  // Exit code and error information
  exit_code?: number;
  error_message?: string;
  error_type?: string;
  traceback?: string;
}

export interface TestStartedEvent extends BaseEvent {
  event_type: 'test_started';
  procedure_file: string;
  total_scenarios: number;
}

export interface TestCompletedEvent extends BaseEvent {
  event_type: 'test_completed';
  result: {
    total_scenarios: number;
    passed_scenarios: number;
    failed_scenarios: number;
    total_cost: number;
    total_tokens: number;
    total_llm_calls: number;
    total_iterations: number;
    unique_tools_used: string[];
    features: Array<{
      name: string;
      scenarios: Array<{
        name: string;
        status: string;
        duration: number;
        steps: Array<{
          keyword: string;
          text: string;
          status: string;
          error_message?: string;
        }>;
      }>;
    }>;
  };
}

export interface TestScenarioStartedEvent extends BaseEvent {
  event_type: 'test_scenario_started';
  scenario_name: string;
}

export interface TestScenarioCompletedEvent extends BaseEvent {
  event_type: 'test_scenario_completed';
  scenario_name: string;
  status: string;
  duration: number;
  total_cost: number;
  total_tokens: number;
  llm_calls: number;
  iterations: number;
  tools_used: string[];
}

export interface EvaluationStartedEvent extends BaseEvent {
  event_type: 'evaluation_started';
  procedure_file: string;
  total_scenarios: number;
  runs_per_scenario: number;
}

export interface EvaluationCompletedEvent extends BaseEvent {
  event_type: 'evaluation_completed';
  results: Array<{
    scenario_name: string;
    total_runs: number;
    successful_runs: number;
    failed_runs: number;
    success_rate: number;
    consistency_score: number;
    is_flaky: boolean;
    avg_duration: number;
    std_duration: number;
  }>;
}

export interface EvaluationProgressEvent extends BaseEvent {
  event_type: 'evaluation_progress';
  scenario_name: string;
  completed_runs: number;
  total_runs: number;
}

export interface LoadingEvent extends BaseEvent {
  event_type: 'loading';
  message: string;
}

export interface AgentStreamChunkEvent extends BaseEvent {
  event_type: 'agent_stream_chunk';
  agent_name: string;
  chunk_text: string;
  accumulated_text: string;
  timestamp: string;
  procedure_id?: string;
}

export type AnyEvent = 
  | LogEvent
  | CostEvent
  | ExecutionEvent 
  | OutputEvent 
  | ValidationEvent 
  | ExecutionSummaryEvent
  | TestStartedEvent
  | TestCompletedEvent
  | TestScenarioStartedEvent
  | TestScenarioCompletedEvent
  | EvaluationStartedEvent
  | EvaluationCompletedEvent
  | EvaluationProgressEvent
  | LoadingEvent
  | AgentStreamChunkEvent;





