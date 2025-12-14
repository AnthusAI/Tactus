import type { Meta, StoryObj } from '@storybook/react';
import { ResultsSidebar } from '../ResultsSidebar';
import { AnyEvent, ExecutionEvent, LogEvent, TestStartedEvent, TestScenarioCompletedEvent, TestCompletedEvent, LoadingEvent } from '@/types/events';

const meta = {
  title: 'Scenarios/Test',
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

export const AllTestsPass: Story = {
  name: 'Test - All Pass',
  render: () => {
    const baseTime = Date.now();
    const timestamp = (offsetMs: number) => new Date(baseTime + offsetMs).toISOString();
    
    const events: AnyEvent[] = [
      {
        event_type: 'execution',
        timestamp: timestamp(0),
        lifecycle_stage: 'start',
        details: { path: 'examples/simple-agent.tac' },
      } as ExecutionEvent,
      {
        event_type: 'test_started',
        timestamp: timestamp(100),
        procedure_file: 'examples/simple-agent.tac',
        total_scenarios: 3,
      } as TestStartedEvent,
      {
        event_type: 'log',
        timestamp: timestamp(200),
        level: 'INFO',
        message: 'Running scenario: Agent responds correctly',
      } as LogEvent,
      {
        event_type: 'test_scenario_completed',
        timestamp: timestamp(2500),
        scenario_name: 'Agent responds correctly',
        status: 'passed',
        duration: 2.3,
        total_cost: 0.025,
        total_tokens: 1800,
        llm_calls: 1,
        iterations: 1,
        tools_used: ['done'],
      } as TestScenarioCompletedEvent,
      {
        event_type: 'log',
        timestamp: timestamp(2600),
        level: 'INFO',
        message: 'Running scenario: Agent handles errors gracefully',
      } as LogEvent,
      {
        event_type: 'test_scenario_completed',
        timestamp: timestamp(4800),
        scenario_name: 'Agent handles errors gracefully',
        status: 'passed',
        duration: 2.2,
        total_cost: 0.022,
        total_tokens: 1600,
        llm_calls: 1,
        iterations: 1,
        tools_used: ['done'],
      } as TestScenarioCompletedEvent,
      {
        event_type: 'log',
        timestamp: timestamp(4900),
        level: 'INFO',
        message: 'Running scenario: Agent uses tools correctly',
      } as LogEvent,
      {
        event_type: 'test_scenario_completed',
        timestamp: timestamp(7500),
        scenario_name: 'Agent uses tools correctly',
        status: 'passed',
        duration: 2.6,
        total_cost: 0.030,
        total_tokens: 2100,
        llm_calls: 1,
        iterations: 2,
        tools_used: ['fetch_data', 'done'],
      } as TestScenarioCompletedEvent,
      {
        event_type: 'test_completed',
        timestamp: timestamp(7600),
        result: {
          total_scenarios: 3,
          passed_scenarios: 3,
          failed_scenarios: 0,
          total_cost: 0.077,
          total_tokens: 5500,
          total_llm_calls: 3,
          total_iterations: 4,
          unique_tools_used: ['fetch_data', 'done'],
          features: [],
        },
      } as TestCompletedEvent,
      {
        event_type: 'execution',
        timestamp: timestamp(7700),
        lifecycle_stage: 'complete',
        exit_code: 0,
      } as ExecutionEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={false} onClear={() => console.log('Clear clicked')} />;
  },
};

export const SomeTestsFail: Story = {
  name: 'Test - Some Failures',
  render: () => {
    const baseTime = Date.now();
    const timestamp = (offsetMs: number) => new Date(baseTime + offsetMs).toISOString();
    
    const events: AnyEvent[] = [
      {
        event_type: 'execution',
        timestamp: timestamp(0),
        lifecycle_stage: 'start',
        details: { path: 'examples/agent-with-issues.tac' },
      } as ExecutionEvent,
      {
        event_type: 'test_started',
        timestamp: timestamp(100),
        procedure_file: 'examples/agent-with-issues.tac',
        total_scenarios: 4,
      } as TestStartedEvent,
      {
        event_type: 'log',
        timestamp: timestamp(200),
        level: 'INFO',
        message: 'Running scenario: Basic functionality works',
      } as LogEvent,
      {
        event_type: 'test_scenario_completed',
        timestamp: timestamp(2200),
        scenario_name: 'Basic functionality works',
        status: 'passed',
        duration: 2.0,
        total_cost: 0.020,
        total_tokens: 1500,
        llm_calls: 1,
        iterations: 1,
        tools_used: ['done'],
      } as TestScenarioCompletedEvent,
      {
        event_type: 'log',
        timestamp: timestamp(2300),
        level: 'INFO',
        message: 'Running scenario: Agent responds with correct format',
      } as LogEvent,
      {
        event_type: 'log',
        timestamp: timestamp(4000),
        level: 'ERROR',
        message: 'Assertion failed: Expected JSON but got plain text',
      } as LogEvent,
      {
        event_type: 'test_scenario_completed',
        timestamp: timestamp(4100),
        scenario_name: 'Agent responds with correct format',
        status: 'failed',
        duration: 1.8,
        total_cost: 0.018,
        total_tokens: 1400,
        llm_calls: 1,
        iterations: 1,
        tools_used: ['done'],
      } as TestScenarioCompletedEvent,
      {
        event_type: 'log',
        timestamp: timestamp(4200),
        level: 'INFO',
        message: 'Running scenario: Agent handles edge cases',
      } as LogEvent,
      {
        event_type: 'test_scenario_completed',
        timestamp: timestamp(6000),
        scenario_name: 'Agent handles edge cases',
        status: 'passed',
        duration: 1.8,
        total_cost: 0.019,
        total_tokens: 1450,
        llm_calls: 1,
        iterations: 1,
        tools_used: ['done'],
      } as TestScenarioCompletedEvent,
      {
        event_type: 'log',
        timestamp: timestamp(6100),
        level: 'INFO',
        message: 'Running scenario: Agent validates input',
      } as LogEvent,
      {
        event_type: 'log',
        timestamp: timestamp(7500),
        level: 'ERROR',
        message: 'Assertion failed: Agent did not reject invalid input',
      } as LogEvent,
      {
        event_type: 'test_scenario_completed',
        timestamp: timestamp(7600),
        scenario_name: 'Agent validates input',
        status: 'failed',
        duration: 1.5,
        total_cost: 0.015,
        total_tokens: 1200,
        llm_calls: 1,
        iterations: 1,
        tools_used: ['done'],
      } as TestScenarioCompletedEvent,
      {
        event_type: 'test_completed',
        timestamp: timestamp(7700),
        result: {
          total_scenarios: 4,
          passed_scenarios: 2,
          failed_scenarios: 2,
          total_cost: 0.072,
          total_tokens: 5550,
          total_llm_calls: 4,
          total_iterations: 4,
          unique_tools_used: ['done'],
          features: [
            {
              name: 'Agent Behavior',
              scenarios: [
                {
                  name: 'Agent responds with correct format',
                  status: 'failed',
                  duration: 1.8,
                  steps: [
                    { keyword: 'Given', text: 'an agent is configured', status: 'passed' },
                    { keyword: 'When', text: 'I send a request', status: 'passed' },
                    { keyword: 'Then', text: 'the response should be JSON', status: 'failed', error_message: 'Expected JSON but got plain text' },
                  ],
                },
                {
                  name: 'Agent validates input',
                  status: 'failed',
                  duration: 1.5,
                  steps: [
                    { keyword: 'Given', text: 'an agent is configured', status: 'passed' },
                    { keyword: 'When', text: 'I send invalid input', status: 'passed' },
                    { keyword: 'Then', text: 'the agent should reject it', status: 'failed', error_message: 'Agent did not reject invalid input' },
                  ],
                },
              ],
            },
          ],
        },
      } as TestCompletedEvent,
      {
        event_type: 'execution',
        timestamp: timestamp(7800),
        lifecycle_stage: 'error',
        exit_code: 1,
      } as ExecutionEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={false} onClear={() => console.log('Clear clicked')} />;
  },
};

export const TestInProgress: Story = {
  name: 'Test - In Progress',
  render: () => {
    const baseTime = Date.now();
    const timestamp = (offsetMs: number) => new Date(baseTime + offsetMs).toISOString();
    
    const events: AnyEvent[] = [
      {
        event_type: 'execution',
        timestamp: timestamp(0),
        lifecycle_stage: 'start',
        details: { path: 'examples/complex-agent.tac' },
      } as ExecutionEvent,
      {
        event_type: 'test_started',
        timestamp: timestamp(100),
        procedure_file: 'examples/complex-agent.tac',
        total_scenarios: 5,
      } as TestStartedEvent,
      {
        event_type: 'log',
        timestamp: timestamp(200),
        level: 'INFO',
        message: 'Running scenario: Agent initializes correctly',
      } as LogEvent,
      {
        event_type: 'test_scenario_completed',
        timestamp: timestamp(2000),
        scenario_name: 'Agent initializes correctly',
        status: 'passed',
        duration: 1.8,
        total_cost: 0.018,
        total_tokens: 1400,
        llm_calls: 1,
        iterations: 1,
        tools_used: ['done'],
      } as TestScenarioCompletedEvent,
      {
        event_type: 'log',
        timestamp: timestamp(2100),
        level: 'INFO',
        message: 'Running scenario: Agent processes complex queries',
      } as LogEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={true} onClear={() => console.log('Clear clicked')} />;
  },
};

export const TestWaitingForScenario: Story = {
  name: 'Test - Waiting for Scenario (with spinner)',
  render: () => {
    const baseTime = Date.now();
    const timestamp = (offsetMs: number) => new Date(baseTime + offsetMs).toISOString();
    
    const events: AnyEvent[] = [
      {
        event_type: 'execution',
        timestamp: timestamp(0),
        lifecycle_stage: 'start',
        details: { path: 'examples/complex-agent.tac' },
      } as ExecutionEvent,
      {
        event_type: 'test_started',
        timestamp: timestamp(100),
        procedure_file: 'examples/complex-agent.tac',
        total_scenarios: 5,
      } as TestStartedEvent,
      {
        event_type: 'log',
        timestamp: timestamp(200),
        level: 'INFO',
        message: 'Running scenario: Agent initializes correctly',
      } as LogEvent,
      {
        event_type: 'test_scenario_completed',
        timestamp: timestamp(2000),
        scenario_name: 'Agent initializes correctly',
        status: 'passed',
        duration: 1.8,
        total_cost: 0.018,
        total_tokens: 1400,
        llm_calls: 1,
        iterations: 1,
        tools_used: ['done'],
      } as TestScenarioCompletedEvent,
      {
        event_type: 'loading',
        timestamp: timestamp(2200),
        message: 'Running scenario: Agent processes complex queries...',
      } as LoadingEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={true} onClear={() => console.log('Clear clicked')} />;
  },
};
