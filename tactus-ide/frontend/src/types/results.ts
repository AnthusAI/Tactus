import { AnyEvent } from './events';

export interface RunHistory {
  id: string;
  timestamp: string;
  operationType: 'validate' | 'test' | 'evaluate' | 'run';
  events: AnyEvent[];
  isExpanded: boolean;
  status: 'running' | 'success' | 'failed' | 'error';
}

export interface FileResultsHistory {
  filePath: string;
  runs: RunHistory[];
}

export interface ResultsHistoryState {
  [filePath: string]: FileResultsHistory;
}
