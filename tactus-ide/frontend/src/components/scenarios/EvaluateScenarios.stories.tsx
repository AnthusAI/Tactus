import type { Meta, StoryObj } from '@storybook/react';
import { ResultsSidebar } from '../ResultsSidebar';
import { AnyEvent, ExecutionEvent, LogEvent, EvaluationStartedEvent, EvaluationProgressEvent, EvaluationCompletedEvent } from '@/types/events';

const meta = {
  title: 'Scenarios/Evaluate',
  component: ResultsSidebar,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div style={{ height: '600px', width: '400px' }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ResultsSidebar>;

export default meta;
type Story = StoryObj<typeof meta>;

// baseTime moved inside render functions
// timestamp helper moved inside render functions

export const PerfectConsistency: Story = {
  name: 'Evaluate - Perfect Consistency',
  render: () => {
    const baseTime = Date.now();
    const timestamp = (offsetMs: number) => new Date(baseTime + offsetMs).toISOString();
    
    const events: AnyEvent[] = [
      {
        event_type: 'execution',
        timestamp: timestamp(0),
        lifecycle_stage: 'start',
        details: { path: 'examples/reliable-agent.tac' },
      } as ExecutionEvent,
      {
        event_type: 'evaluation_started',
        timestamp: timestamp(100),
        procedure_file: 'examples/reliable-agent.tac',
        total_scenarios: 3,
        runs_per_scenario: 10,
      } as EvaluationStartedEvent,
      {
        event_type: 'log',
        timestamp: timestamp(200),
        level: 'INFO',
        message: 'Starting evaluation with 10 runs per scenario',
      } as LogEvent,
      {
        event_type: 'evaluation_progress',
        timestamp: timestamp(2000),
        scenario_name: 'Agent responds correctly',
        completed_runs: 3,
        total_runs: 10,
      } as EvaluationProgressEvent,
      {
        event_type: 'evaluation_progress',
        timestamp: timestamp(4000),
        scenario_name: 'Agent responds correctly',
        completed_runs: 6,
        total_runs: 10,
      } as EvaluationProgressEvent,
      {
        event_type: 'evaluation_progress',
        timestamp: timestamp(6000),
        scenario_name: 'Agent responds correctly',
        completed_runs: 10,
        total_runs: 10,
      } as EvaluationProgressEvent,
      {
        event_type: 'log',
        timestamp: timestamp(6100),
        level: 'INFO',
        message: 'Completed scenario: Agent responds correctly (10/10 passed)',
      } as LogEvent,
      {
        event_type: 'evaluation_progress',
        timestamp: timestamp(8000),
        scenario_name: 'Agent handles errors',
        completed_runs: 5,
        total_runs: 10,
      } as EvaluationProgressEvent,
      {
        event_type: 'evaluation_progress',
        timestamp: timestamp(10000),
        scenario_name: 'Agent handles errors',
        completed_runs: 10,
        total_runs: 10,
      } as EvaluationProgressEvent,
      {
        event_type: 'log',
        timestamp: timestamp(10100),
        level: 'INFO',
        message: 'Completed scenario: Agent handles errors (10/10 passed)',
      } as LogEvent,
      {
        event_type: 'evaluation_progress',
        timestamp: timestamp(12000),
        scenario_name: 'Agent uses tools',
        completed_runs: 5,
        total_runs: 10,
      } as EvaluationProgressEvent,
      {
        event_type: 'evaluation_progress',
        timestamp: timestamp(14000),
        scenario_name: 'Agent uses tools',
        completed_runs: 10,
        total_runs: 10,
      } as EvaluationProgressEvent,
      {
        event_type: 'log',
        timestamp: timestamp(14100),
        level: 'INFO',
        message: 'Completed scenario: Agent uses tools (10/10 passed)',
      } as LogEvent,
      {
        event_type: 'evaluation_completed',
        timestamp: timestamp(14200),
        results: [
          {
            scenario_name: 'Agent responds correctly',
            total_runs: 10,
            successful_runs: 10,
            failed_runs: 0,
            success_rate: 1.0,
            consistency_score: 1.0,
            is_flaky: false,
            avg_duration: 2.3,
            std_duration: 0.1,
          },
          {
            scenario_name: 'Agent handles errors',
            total_runs: 10,
            successful_runs: 10,
            failed_runs: 0,
            success_rate: 1.0,
            consistency_score: 1.0,
            is_flaky: false,
            avg_duration: 2.1,
            std_duration: 0.08,
          },
          {
            scenario_name: 'Agent uses tools',
            total_runs: 10,
            successful_runs: 10,
            failed_runs: 0,
            success_rate: 1.0,
            consistency_score: 1.0,
            is_flaky: false,
            avg_duration: 2.8,
            std_duration: 0.15,
          },
        ],
      } as EvaluationCompletedEvent,
      {
        event_type: 'execution',
        timestamp: timestamp(14300),
        lifecycle_stage: 'complete',
        exit_code: 0,
      } as ExecutionEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={false} onClear={() => console.log('Clear clicked')} />;
  },
};

export const FlakyBehavior: Story = {
  name: 'Evaluate - Flaky Tests Detected',
  render: () => {
    const baseTime = Date.now();
    const timestamp = (offsetMs: number) => new Date(baseTime + offsetMs).toISOString();
    
    const events: AnyEvent[] = [
      {
        event_type: 'execution',
        timestamp: timestamp(0),
        lifecycle_stage: 'start',
        details: { path: 'examples/unreliable-agent.tac' },
      } as ExecutionEvent,
      {
        event_type: 'evaluation_started',
        timestamp: timestamp(100),
        procedure_file: 'examples/unreliable-agent.tac',
        total_scenarios: 2,
        runs_per_scenario: 10,
      } as EvaluationStartedEvent,
      {
        event_type: 'log',
        timestamp: timestamp(200),
        level: 'INFO',
        message: 'Starting consistency evaluation',
      } as LogEvent,
      {
        event_type: 'evaluation_progress',
        timestamp: timestamp(2000),
        scenario_name: 'Stable scenario',
        completed_runs: 5,
        total_runs: 10,
      } as EvaluationProgressEvent,
      {
        event_type: 'evaluation_progress',
        timestamp: timestamp(4000),
        scenario_name: 'Stable scenario',
        completed_runs: 10,
        total_runs: 10,
      } as EvaluationProgressEvent,
      {
        event_type: 'log',
        timestamp: timestamp(4100),
        level: 'INFO',
        message: 'Completed scenario: Stable scenario (10/10 passed)',
      } as LogEvent,
      {
        event_type: 'evaluation_progress',
        timestamp: timestamp(6000),
        scenario_name: 'Flaky scenario',
        completed_runs: 3,
        total_runs: 10,
      } as EvaluationProgressEvent,
      {
        event_type: 'log',
        timestamp: timestamp(7000),
        level: 'WARNING',
        message: 'Run 4 failed for: Flaky scenario',
      } as LogEvent,
      {
        event_type: 'evaluation_progress',
        timestamp: timestamp(8000),
        scenario_name: 'Flaky scenario',
        completed_runs: 6,
        total_runs: 10,
      } as EvaluationProgressEvent,
      {
        event_type: 'log',
        timestamp: timestamp(9000),
        level: 'WARNING',
        message: 'Run 7 failed for: Flaky scenario',
      } as LogEvent,
      {
        event_type: 'evaluation_progress',
        timestamp: timestamp(10000),
        scenario_name: 'Flaky scenario',
        completed_runs: 10,
        total_runs: 10,
      } as EvaluationProgressEvent,
      {
        event_type: 'log',
        timestamp: timestamp(10100),
        level: 'WARNING',
        message: 'Completed scenario: Flaky scenario (7/10 passed) - FLAKY BEHAVIOR DETECTED',
      } as LogEvent,
      {
        event_type: 'evaluation_completed',
        timestamp: timestamp(10200),
        results: [
          {
            scenario_name: 'Stable scenario',
            total_runs: 10,
            successful_runs: 10,
            failed_runs: 0,
            success_rate: 1.0,
            consistency_score: 1.0,
            is_flaky: false,
            avg_duration: 2.2,
            std_duration: 0.09,
          },
          {
            scenario_name: 'Flaky scenario',
            total_runs: 10,
            successful_runs: 7,
            failed_runs: 3,
            success_rate: 0.7,
            consistency_score: 0.65,
            is_flaky: true,
            avg_duration: 2.5,
            std_duration: 0.9,
          },
        ],
      } as EvaluationCompletedEvent,
      {
        event_type: 'execution',
        timestamp: timestamp(10300),
        lifecycle_stage: 'complete',
        exit_code: 0,
      } as ExecutionEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={false} onClear={() => console.log('Clear clicked')} />;
  },
};

export const EvaluateInProgress: Story = {
  name: 'Evaluate - In Progress',
  render: () => {
    const baseTime = Date.now();
    const timestamp = (offsetMs: number) => new Date(baseTime + offsetMs).toISOString();
    
    const events: AnyEvent[] = [
      {
        event_type: 'execution',
        timestamp: timestamp(0),
        lifecycle_stage: 'start',
        details: { path: 'examples/agent-under-test.tac' },
      } as ExecutionEvent,
      {
        event_type: 'evaluation_started',
        timestamp: timestamp(100),
        procedure_file: 'examples/agent-under-test.tac',
        total_scenarios: 4,
        runs_per_scenario: 10,
      } as EvaluationStartedEvent,
      {
        event_type: 'log',
        timestamp: timestamp(200),
        level: 'INFO',
        message: 'Starting evaluation: 4 scenarios × 10 runs = 40 total runs',
      } as LogEvent,
      {
        event_type: 'evaluation_progress',
        timestamp: timestamp(2000),
        scenario_name: 'Basic functionality',
        completed_runs: 3,
        total_runs: 10,
      } as EvaluationProgressEvent,
      {
        event_type: 'evaluation_progress',
        timestamp: timestamp(4000),
        scenario_name: 'Basic functionality',
        completed_runs: 7,
        total_runs: 10,
      } as EvaluationProgressEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={true} onClear={() => console.log('Clear clicked')} />;
  },
};
