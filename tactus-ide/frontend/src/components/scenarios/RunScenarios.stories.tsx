import type { Meta, StoryObj } from '@storybook/react';
import { ResultsSidebar } from '../ResultsSidebar';
import { AnyEvent, ExecutionEvent, LogEvent, CostEvent, ExecutionSummaryEvent, OutputEvent, LoadingEvent } from '@/types/events';

const meta = {
  title: 'Scenarios/Run',
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

export const SimpleRunSuccess: Story = {
  name: 'Run - Simple Success',
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
        event_type: 'log',
        timestamp: timestamp(100),
        level: 'INFO',
        message: 'Initializing agent: my_agent',
      } as LogEvent,
      {
        event_type: 'log',
        timestamp: timestamp(200),
        level: 'INFO',
        message: 'Agent started with model: gpt-4o',
      } as LogEvent,
      {
        event_type: 'log',
        timestamp: timestamp(300),
        level: 'INFO',
        message: 'Sending request to LLM',
      } as LogEvent,
      {
        event_type: 'cost',
        timestamp: timestamp(2000),
        agent_name: 'my_agent',
        model: 'gpt-4o',
        provider: 'openai',
        prompt_tokens: 150,
        completion_tokens: 50,
        total_tokens: 200,
        prompt_cost: 0.0015,
        completion_cost: 0.0015,
        total_cost: 0.003,
        retry_count: 0,
        validation_errors: [],
        cache_hit: false,
        message_count: 2,
        new_message_count: 1,
      } as CostEvent,
      {
        event_type: 'execution_summary',
        timestamp: timestamp(2500),
        result: { status: 'success', message: 'Task completed' },
        final_state: {},
        iterations: 1,
        tools_used: [],
        total_cost: 0.003,
        total_tokens: 200,
        cost_breakdown: [],
      } as ExecutionSummaryEvent,
      {
        event_type: 'execution',
        timestamp: timestamp(2800),
        lifecycle_stage: 'complete',
        exit_code: 0,
      } as ExecutionEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={false} onClear={() => console.log('Clear clicked')} />;
  },
};

export const RunWithMultipleIterations: Story = {
  name: 'Run - Multiple Iterations',
  render: () => {
    const baseTime = Date.now();
    const timestamp = (offsetMs: number) => new Date(baseTime + offsetMs).toISOString();
    
    const events: AnyEvent[] = [
      {
        event_type: 'execution',
        timestamp: timestamp(0),
        lifecycle_stage: 'start',
        details: { path: 'examples/multi-iteration.tac' },
      } as ExecutionEvent,
      {
        event_type: 'log',
        timestamp: timestamp(100),
        level: 'INFO',
        message: 'Starting iteration 1',
      } as LogEvent,
      {
        event_type: 'cost',
        timestamp: timestamp(1000),
        agent_name: 'my_agent',
        model: 'gpt-4o',
        provider: 'openai',
        prompt_tokens: 150,
        completion_tokens: 50,
        total_tokens: 200,
        prompt_cost: 0.0015,
        completion_cost: 0.0015,
        total_cost: 0.003,
        retry_count: 0,
        validation_errors: [],
        cache_hit: false,
        message_count: 2,
        new_message_count: 1,
      } as CostEvent,
      {
        event_type: 'log',
        timestamp: timestamp(1200),
        level: 'INFO',
        message: 'Starting iteration 2',
      } as LogEvent,
      {
        event_type: 'cost',
        timestamp: timestamp(2000),
        agent_name: 'my_agent',
        model: 'gpt-4o',
        provider: 'openai',
        prompt_tokens: 180,
        completion_tokens: 60,
        total_tokens: 240,
        prompt_cost: 0.0018,
        completion_cost: 0.0018,
        total_cost: 0.0036,
        retry_count: 0,
        validation_errors: [],
        cache_hit: false,
        message_count: 3,
        new_message_count: 1,
      } as CostEvent,
      {
        event_type: 'log',
        timestamp: timestamp(2200),
        level: 'INFO',
        message: 'Starting iteration 3',
      } as LogEvent,
      {
        event_type: 'cost',
        timestamp: timestamp(3000),
        agent_name: 'my_agent',
        model: 'gpt-4o',
        provider: 'openai',
        prompt_tokens: 200,
        completion_tokens: 70,
        total_tokens: 270,
        prompt_cost: 0.002,
        completion_cost: 0.0021,
        total_cost: 0.0041,
        retry_count: 0,
        validation_errors: [],
        cache_hit: false,
        message_count: 4,
        new_message_count: 1,
      } as CostEvent,
      {
        event_type: 'execution_summary',
        timestamp: timestamp(3500),
        result: { status: 'success', iterations: 3 },
        final_state: {},
        iterations: 3,
        tools_used: [],
        total_cost: 0.0107,
        total_tokens: 710,
        cost_breakdown: [],
      } as ExecutionSummaryEvent,
      {
        event_type: 'execution',
        timestamp: timestamp(3800),
        lifecycle_stage: 'complete',
        exit_code: 0,
      } as ExecutionEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={false} onClear={() => console.log('Clear clicked')} />;
  },
};

export const RunWithError: Story = {
  name: 'Run - With Error',
  render: () => {
    const baseTime = Date.now();
    const timestamp = (offsetMs: number) => new Date(baseTime + offsetMs).toISOString();
    
    const events: AnyEvent[] = [
      {
        event_type: 'execution',
        timestamp: timestamp(0),
        lifecycle_stage: 'start',
        details: { path: 'examples/failing-agent.tac' },
      } as ExecutionEvent,
      {
        event_type: 'log',
        timestamp: timestamp(100),
        level: 'INFO',
        message: 'Starting agent',
      } as LogEvent,
      {
        event_type: 'log',
        timestamp: timestamp(500),
        level: 'ERROR',
        message: 'Failed to connect to LLM provider',
      } as LogEvent,
      {
        event_type: 'log',
        timestamp: timestamp(600),
        level: 'ERROR',
        message: 'Connection timeout after 30s',
      } as LogEvent,
      {
        event_type: 'execution',
        timestamp: timestamp(800),
        lifecycle_stage: 'error',
        exit_code: 1,
        details: { error: 'Connection timeout' },
      } as ExecutionEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={false} onClear={() => console.log('Clear clicked')} />;
  },
};

export const RunInProgress: Story = {
  name: 'Run - In Progress (with spinner)',
  render: () => {
    const baseTime = Date.now();
    const timestamp = (offsetMs: number) => new Date(baseTime + offsetMs).toISOString();
    
    const events: AnyEvent[] = [
      {
        event_type: 'execution',
        timestamp: timestamp(0),
        lifecycle_stage: 'start',
        details: { path: 'examples/long-running-agent.tac' },
      } as ExecutionEvent,
      {
        event_type: 'log',
        timestamp: timestamp(100),
        level: 'INFO',
        message: 'Starting long-running process',
      } as LogEvent,
      {
        event_type: 'loading',
        timestamp: timestamp(300),
        message: 'Initializing agent...',
      } as LoadingEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={true} onClear={() => console.log('Clear clicked')} />;
  },
};

export const RunWaitingForLLM: Story = {
  name: 'Run - Waiting for LLM (with spinner)',
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
        event_type: 'log',
        timestamp: timestamp(100),
        level: 'INFO',
        message: 'Agent initialized',
      } as LogEvent,
      {
        event_type: 'log',
        timestamp: timestamp(200),
        level: 'INFO',
        message: 'Preparing request to LLM',
      } as LogEvent,
      {
        event_type: 'loading',
        timestamp: timestamp(400),
        message: 'Sending request to LLM...',
      } as LoadingEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={true} onClear={() => console.log('Clear clicked')} />;
  },
};
