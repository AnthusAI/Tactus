import type { Meta, StoryObj } from '@storybook/react';
import { TestCompletedEventComponent, TestScenarioCompletedEventComponent, TestStartedEventComponent } from './TestEventComponent';
import { TestStartedEvent, TestCompletedEvent, TestScenarioCompletedEvent } from '@/types/events';

const baseTimestamp = new Date().toISOString();

// TestStartedEventComponent
const testStartedMeta = {
  title: 'Events/Test/TestStartedEventComponent',
  component: TestStartedEventComponent,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof TestStartedEventComponent>;

export default testStartedMeta;
type TestStartedStory = StoryObj<typeof testStartedMeta>;

export const TestStarted: TestStartedStory = {
  args: {
    event: {
      event_type: 'test_started',
      timestamp: baseTimestamp,
      procedure_file: 'examples/simple-agent.tac',
      total_scenarios: 5,
    } as TestStartedEvent,
  },
};

// TestScenarioCompletedEventComponent
const scenarioMeta = {
  title: 'Events/Test/TestScenarioCompletedEventComponent',
  component: TestScenarioCompletedEventComponent,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof TestScenarioCompletedEventComponent>;

export const ScenarioPassed: StoryObj<typeof scenarioMeta> = {
  args: {
    event: {
      event_type: 'test_scenario_completed',
      timestamp: baseTimestamp,
      scenario_name: 'Agent responds correctly',
      status: 'passed',
      duration: 2.5,
      total_cost: 0.03,
      total_tokens: 2000,
      llm_calls: 1,
      iterations: 1,
      tools_used: ['done'],
    } as TestScenarioCompletedEvent,
  },
};

export const ScenarioFailed: StoryObj<typeof scenarioMeta> = {
  args: {
    event: {
      event_type: 'test_scenario_completed',
      timestamp: baseTimestamp,
      scenario_name: 'Agent handles error gracefully',
      status: 'failed',
      duration: 1.8,
      total_cost: 0.02,
      total_tokens: 1500,
      llm_calls: 1,
      iterations: 1,
      tools_used: ['done'],
    } as TestScenarioCompletedEvent,
  },
};

// TestCompletedEventComponent
const completedMeta = {
  title: 'Events/Test/TestCompletedEventComponent',
  component: TestCompletedEventComponent,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof TestCompletedEventComponent>;

export const AllTestsPassed: StoryObj<typeof completedMeta> = {
  args: {
    event: {
      event_type: 'test_completed',
      timestamp: baseTimestamp,
      result: {
        total_scenarios: 5,
        passed_scenarios: 5,
        failed_scenarios: 0,
        total_cost: 0.15,
        total_tokens: 10000,
        total_llm_calls: 5,
        total_iterations: 5,
        unique_tools_used: ['done'],
        features: [],
      },
    } as TestCompletedEvent,
  },
};

export const SomeTestsFailed: StoryObj<typeof completedMeta> = {
  args: {
    event: {
      event_type: 'test_completed',
      timestamp: baseTimestamp,
      result: {
        total_scenarios: 5,
        passed_scenarios: 3,
        failed_scenarios: 2,
        total_cost: 0.12,
        total_tokens: 8000,
        total_llm_calls: 5,
        total_iterations: 7,
        unique_tools_used: ['fetch_data', 'process', 'done'],
        features: [
          {
            name: 'Basic Agent Behavior',
            scenarios: [
              {
                name: 'Agent responds to simple query',
                status: 'failed',
                duration: 2.5,
                steps: [
                  { keyword: 'Given', text: 'an agent is configured', status: 'passed' },
                  { keyword: 'When', text: 'I send a query', status: 'passed' },
                  { keyword: 'Then', text: 'the response should contain "hello"', status: 'failed', error_message: 'Expected "hello" but got "hi"' },
                ],
              },
              {
                name: 'Agent handles invalid input',
                status: 'failed',
                duration: 1.8,
                steps: [
                  { keyword: 'Given', text: 'an agent is configured', status: 'passed' },
                  { keyword: 'When', text: 'I send invalid input', status: 'passed' },
                  { keyword: 'Then', text: 'the agent should return an error', status: 'failed', error_message: 'Agent did not return error as expected' },
                ],
              },
            ],
          },
        ],
      },
    } as TestCompletedEvent,
  },
};

export const WithUndefinedSteps: StoryObj<typeof completedMeta> = {
  args: {
    event: {
      event_type: 'test_completed',
      timestamp: baseTimestamp,
      result: {
        total_scenarios: 3,
        passed_scenarios: 1,
        failed_scenarios: 2,
        total_cost: 0.05,
        total_tokens: 3000,
        total_llm_calls: 1,
        total_iterations: 1,
        unique_tools_used: ['done'],
        features: [
          {
            name: 'New Feature',
            scenarios: [
              {
                name: 'Unimplemented scenario',
                status: 'failed',
                duration: 0.1,
                steps: [
                  { keyword: 'Given', text: 'a new feature', status: 'undefined' },
                  { keyword: 'When', text: 'I use it', status: 'skipped' },
                  { keyword: 'Then', text: 'it should work', status: 'skipped' },
                ],
              },
            ],
          },
        ],
      },
    } as TestCompletedEvent,
  },
};
