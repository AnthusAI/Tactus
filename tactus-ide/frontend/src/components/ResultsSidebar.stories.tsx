import type { Meta, StoryObj } from '@storybook/react';
import { ResultsSidebar } from './ResultsSidebar';
import { AnyEvent, LogEvent, ExecutionEvent, ValidationEvent, CostEvent, ExecutionSummaryEvent } from '@/types/events';

const meta = {
  title: 'Layout/ResultsSidebar',
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

const baseTimestamp = new Date().toISOString();

export const Empty: Story = {
  args: {
    events: [],
    isRunning: false,
    onClear: () => console.log('Clear clicked'),
  },
};

export const Running: Story = {
  args: {
    events: [
      {
        event_type: 'log',
        timestamp: baseTimestamp,
        level: 'INFO',
        message: 'Starting execution...',
      } as LogEvent,
      {
        event_type: 'execution',
        timestamp: baseTimestamp,
        lifecycle_stage: 'start',
      } as ExecutionEvent,
    ],
    isRunning: true,
    onClear: () => console.log('Clear clicked'),
  },
};

export const WithValidationSuccess: Story = {
  args: {
    events: [
      {
        event_type: 'validation',
        timestamp: baseTimestamp,
        valid: true,
        errors: [],
      } as ValidationEvent,
    ],
    isRunning: false,
    onClear: () => console.log('Clear clicked'),
  },
};

export const WithValidationErrors: Story = {
  args: {
    events: [
      {
        event_type: 'validation',
        timestamp: baseTimestamp,
        valid: false,
        errors: [
          { message: 'Undefined variable "foo"', line: 10, column: 5, severity: 'error' },
          { message: 'Missing required field "model"', line: 15, severity: 'error' },
        ],
      } as ValidationEvent,
    ],
    isRunning: false,
    onClear: () => console.log('Clear clicked'),
  },
};

export const WithExecutionComplete: Story = {
  args: {
    events: [
      {
        event_type: 'log',
        timestamp: baseTimestamp,
        level: 'INFO',
        message: 'Starting agent execution',
      } as LogEvent,
      {
        event_type: 'cost',
        timestamp: baseTimestamp,
        agent_name: 'my_agent',
        model: 'gpt-4o',
        provider: 'openai',
        prompt_tokens: 1500,
        completion_tokens: 500,
        total_tokens: 2000,
        prompt_cost: 0.015,
        completion_cost: 0.015,
        total_cost: 0.03,
        retry_count: 0,
        validation_errors: [],
        cache_hit: false,
        message_count: 3,
        new_message_count: 1,
        duration_ms: 2500,
      } as CostEvent,
      {
        event_type: 'execution_summary',
        timestamp: baseTimestamp,
        result: { status: 'success', output: 'Task completed' },
        final_state: { counter: 5 },
        iterations: 1,
        tools_used: ['done'],
        total_cost: 0.03,
        total_tokens: 2000,
        cost_breakdown: [],
      } as ExecutionSummaryEvent,
    ],
    isRunning: false,
    onClear: () => console.log('Clear clicked'),
  },
};

export const WithManyLogs: Story = {
  args: {
    events: Array.from({ length: 50 }, (_, i) => ({
      event_type: 'log',
      timestamp: new Date(Date.now() + i * 1000).toISOString(),
      level: i % 5 === 0 ? 'ERROR' : i % 3 === 0 ? 'WARNING' : 'INFO',
      message: `Log message ${i + 1}`,
    })) as LogEvent[],
    isRunning: false,
    onClear: () => console.log('Clear clicked'),
  },
};
