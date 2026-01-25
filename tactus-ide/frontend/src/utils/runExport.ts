import * as yaml from 'js-yaml';
import { RunHistory } from '@/types/results';

export interface RunExportPayload {
  run: {
    id: string;
    timestamp: string;
    operationType: RunHistory['operationType'];
    status: RunHistory['status'];
  };
  inputs: Record<string, any>;
  events: RunHistory['events'];
  checkpoints: RunHistory['checkpoints'];
}

export function buildRunExportPayload(run: RunHistory): RunExportPayload {
  return {
    run: {
      id: run.id,
      timestamp: run.timestamp,
      operationType: run.operationType,
      status: run.status,
    },
    inputs: run.inputs ?? {},
    events: run.events ?? [],
    checkpoints: run.checkpoints ?? [],
  };
}

export function serializeRunToYaml(run: RunHistory): string {
  const payload = buildRunExportPayload(run);

  return yaml.dump(payload, {
    indent: 2,
    lineWidth: -1,
    noRefs: true,
    sortKeys: false,
  });
}
