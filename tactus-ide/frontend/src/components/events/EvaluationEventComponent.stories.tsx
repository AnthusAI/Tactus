import type { Meta, StoryObj } from '@storybook/react';
import { EvaluationStartedEventComponent, EvaluationProgressEventComponent, EvaluationCompletedEventComponent } from './EvaluationEventComponent';
import { EvaluationStartedEvent, EvaluationProgressEvent, EvaluationCompletedEvent } from '@/types/events';

const baseTimestamp = new Date().toISOString();

// EvaluationStartedEventComponent
const startedMeta = {
  title: 'Events/Evaluation/EvaluationStartedEventComponent',
  component: EvaluationStartedEventComponent,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof EvaluationStartedEventComponent>;

export default startedMeta;
type StartedStory = StoryObj<typeof startedMeta>;

export const EvaluationStarted: StartedStory = {
  args: {
    event: {
      event_type: 'evaluation_started',
      timestamp: baseTimestamp,
      procedure_file: 'examples/simple-agent.tac',
      total_scenarios: 3,
      runs_per_scenario: 10,
    } as EvaluationStartedEvent,
  },
};

// EvaluationProgressEventComponent
const progressMeta = {
  title: 'Events/Evaluation/EvaluationProgressEventComponent',
  component: EvaluationProgressEventComponent,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof EvaluationProgressEventComponent>;

export const Progress25Percent: StoryObj<typeof progressMeta> = {
  args: {
    event: {
      event_type: 'evaluation_progress',
      timestamp: baseTimestamp,
      scenario_name: 'Agent responds correctly',
      completed_runs: 3,
      total_runs: 10,
    } as EvaluationProgressEvent,
  },
};

export const Progress75Percent: StoryObj<typeof progressMeta> = {
  args: {
    event: {
      event_type: 'evaluation_progress',
      timestamp: baseTimestamp,
      scenario_name: 'Agent handles complex queries',
      completed_runs: 8,
      total_runs: 10,
    } as EvaluationProgressEvent,
  },
};

// EvaluationCompletedEventComponent
const completedMeta = {
  title: 'Events/Evaluation/EvaluationCompletedEventComponent',
  component: EvaluationCompletedEventComponent,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof EvaluationCompletedEventComponent>;

export const PerfectConsistency: StoryObj<typeof completedMeta> = {
  args: {
    event: {
      event_type: 'evaluation_completed',
      timestamp: baseTimestamp,
      results: [
        {
          scenario_name: 'Agent responds correctly',
          total_runs: 10,
          successful_runs: 10,
          failed_runs: 0,
          success_rate: 1.0,
          consistency_score: 1.0,
          is_flaky: false,
          avg_duration: 2.5,
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
          avg_duration: 1.8,
          std_duration: 0.05,
        },
      ],
    } as EvaluationCompletedEvent,
  },
};

export const FlakyTests: StoryObj<typeof completedMeta> = {
  args: {
    event: {
      event_type: 'evaluation_completed',
      timestamp: baseTimestamp,
      results: [
        {
          scenario_name: 'Agent responds correctly',
          total_runs: 10,
          successful_runs: 10,
          failed_runs: 0,
          success_rate: 1.0,
          consistency_score: 1.0,
          is_flaky: false,
          avg_duration: 2.5,
          std_duration: 0.1,
        },
        {
          scenario_name: 'Agent handles complex queries',
          total_runs: 10,
          successful_runs: 7,
          failed_runs: 3,
          success_rate: 0.7,
          consistency_score: 0.65,
          is_flaky: true,
          avg_duration: 3.2,
          std_duration: 0.8,
        },
      ],
    } as EvaluationCompletedEvent,
  },
};

export const MixedResults: StoryObj<typeof completedMeta> = {
  args: {
    event: {
      event_type: 'evaluation_completed',
      timestamp: baseTimestamp,
      results: [
        {
          scenario_name: 'Basic functionality',
          total_runs: 10,
          successful_runs: 10,
          failed_runs: 0,
          success_rate: 1.0,
          consistency_score: 1.0,
          is_flaky: false,
          avg_duration: 1.5,
          std_duration: 0.05,
        },
        {
          scenario_name: 'Edge cases',
          total_runs: 10,
          successful_runs: 8,
          failed_runs: 2,
          success_rate: 0.8,
          consistency_score: 0.75,
          is_flaky: true,
          avg_duration: 2.8,
          std_duration: 0.6,
        },
        {
          scenario_name: 'Error handling',
          total_runs: 10,
          successful_runs: 5,
          failed_runs: 5,
          success_rate: 0.5,
          consistency_score: 0.4,
          is_flaky: true,
          avg_duration: 2.2,
          std_duration: 1.2,
        },
      ],
    } as EvaluationCompletedEvent,
  },
};
