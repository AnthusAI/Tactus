import * as yaml from 'js-yaml';
import { serializeRunToYaml } from '../src/utils/runExport';
import { RunHistory } from '../src/types/results';

describe('serializeRunToYaml', () => {
  it('includes full run data in YAML output', () => {
    const run: RunHistory = {
      id: 'run-123',
      timestamp: '2026-01-23T12:00:00Z',
      operationType: 'run',
      status: 'error',
      isExpanded: false,
      inputs: {
        message: 'hello',
      },
      events: [
        {
          type: 'log',
          level: 'error',
          message: 'Something failed',
          details: {
            code: 'E_TEST',
          },
        } as any,
      ],
      checkpoints: [
        {
          position: 1,
          type: 'checkpoint',
          result: { ok: false },
          timestamp: '2026-01-23T12:00:01Z',
          captured_vars: {
            reason: 'missing input',
          },
          source_location: {
            file: '/tmp/example.tac',
            line: 12,
            column: 3,
          },
        },
      ],
    };

    const yamlOutput = serializeRunToYaml(run);
    const parsed = yaml.load(yamlOutput) as Record<string, any>;

    expect(parsed.run.status).toBe('error');
    expect(parsed.inputs.message).toBe('hello');
    expect(parsed.events[0].message).toBe('Something failed');
    expect(parsed.checkpoints[0].captured_vars.reason).toBe('missing input');
  });
});
