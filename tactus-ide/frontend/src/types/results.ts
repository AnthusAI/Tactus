import { AnyEvent } from './events';
import { CheckpointEntry } from './tracing';

export interface RunHistory {
  id: string;
  timestamp: string;
  operationType: 'validate' | 'test' | 'evaluate' | 'run';
  events: AnyEvent[];
  isExpanded: boolean;
  status: 'running' | 'success' | 'failed' | 'error';
  checkpoints?: CheckpointEntry[];
  inputs?: Record<string, any>;  // Input parameters used for this run
}

export interface FileResultsHistory {
  filePath: string;
  runs: RunHistory[];
}

export interface ResultsHistoryState {
  [filePath: string]: FileResultsHistory;
}
