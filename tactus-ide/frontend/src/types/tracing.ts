/**
 * Type definitions for execution tracing and debugging features.
 */

export interface SourceLocation {
  file: string;
  line: number;
  function?: string;
  code_context?: string;
}

export interface CheckpointEntry {
  position: number;
  type: string;
  result: any;
  timestamp: string;
  duration_ms?: number;
  source_location?: SourceLocation;
  captured_vars?: Record<string, any>;
}

export interface Breakpoint {
  breakpoint_id: string;
  file: string;
  line: number;
  condition?: string;
  enabled: boolean;
  hit_count: number;
}

export interface ExecutionRun {
  run_id: string;
  procedure_name: string;
  file_path: string;
  start_time: string;
  end_time?: string;
  status: "RUNNING" | "PAUSED" | "COMPLETED" | "FAILED";
  execution_log: CheckpointEntry[];
  final_state: Record<string, any>;
  breakpoints: Breakpoint[];
}

export interface RunListItem {
  run_id: string;
  procedure_name: string;
  file_path: string;
  start_time: string;
  end_time?: string;
  status: "RUNNING" | "PAUSED" | "COMPLETED" | "FAILED";
  checkpoint_count: number;
}

export interface RunStatistics {
  run_id: string;
  procedure: string;
  status: string;
  total_checkpoints: number;
  checkpoints_by_type: Record<string, number>;
  total_duration_ms: number;
  total_time_sec?: number;
  has_source_locations: number;
}

export interface ComparisonResult {
  run1: {
    id: string;
    procedure: string;
    status: string;
    checkpoint_count: number;
  };
  run2: {
    id: string;
    procedure: string;
    status: string;
    checkpoint_count: number;
  };
  differences: Array<{
    type: string;
    position?: number;
    [key: string]: any;
  }>;
}
