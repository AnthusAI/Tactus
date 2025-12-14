import type { Meta, StoryObj } from '@storybook/react';
import { ResultsSidebar } from '../ResultsSidebar';
import { AnyEvent, ExecutionEvent, LogEvent, ValidationEvent } from '@/types/events';

const meta = {
  title: 'Scenarios/Validation',
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

export const ValidationSuccess: Story = {
  name: 'Validation - Success',
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
        message: 'Starting validation...',
      } as LogEvent,
      {
        event_type: 'log',
        timestamp: timestamp(200),
        level: 'INFO',
        message: 'Parsing Lua syntax...',
      } as LogEvent,
      {
        event_type: 'log',
        timestamp: timestamp(300),
        level: 'INFO',
        message: 'Checking semantic rules...',
      } as LogEvent,
      {
        event_type: 'validation',
        timestamp: timestamp(400),
        valid: true,
        errors: [],
      } as ValidationEvent,
      {
        event_type: 'execution',
        timestamp: timestamp(500),
        lifecycle_stage: 'complete',
        exit_code: 0,
      } as ExecutionEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={false} onClear={() => console.log('Clear clicked')} />;
  },
};

export const ValidationWithErrors: Story = {
  name: 'Validation - With Errors',
  render: () => {
    const baseTime = Date.now();
    const timestamp = (offsetMs: number) => new Date(baseTime + offsetMs).toISOString();
    
    const events: AnyEvent[] = [
      {
        event_type: 'execution',
        timestamp: timestamp(0),
        lifecycle_stage: 'start',
        details: { path: 'examples/broken-agent.tac' },
      } as ExecutionEvent,
      {
        event_type: 'log',
        timestamp: timestamp(100),
        level: 'INFO',
        message: 'Starting validation...',
      } as LogEvent,
      {
        event_type: 'log',
        timestamp: timestamp(200),
        level: 'INFO',
        message: 'Parsing Lua syntax...',
      } as LogEvent,
      {
        event_type: 'log',
        timestamp: timestamp(300),
        level: 'WARNING',
        message: 'Found potential issues',
      } as LogEvent,
      {
        event_type: 'validation',
        timestamp: timestamp(400),
        valid: false,
        errors: [
          {
            message: 'Undefined variable "result"',
            line: 15,
            column: 10,
            severity: 'error',
          },
          {
            message: 'Missing required field "model"',
            line: 8,
            severity: 'error',
          },
          {
            message: 'Invalid provider "unknown"',
            line: 12,
            column: 20,
            severity: 'error',
          },
        ],
      } as ValidationEvent,
      {
        event_type: 'log',
        timestamp: timestamp(500),
        level: 'ERROR',
        message: 'Validation failed with 3 errors',
      } as LogEvent,
      {
        event_type: 'execution',
        timestamp: timestamp(600),
        lifecycle_stage: 'error',
        exit_code: 1,
      } as ExecutionEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={false} onClear={() => console.log('Clear clicked')} />;
  },
};

export const ValidationInProgress: Story = {
  name: 'Validation - In Progress',
  render: () => {
    const baseTime = Date.now();
    const timestamp = (offsetMs: number) => new Date(baseTime + offsetMs).toISOString();
    
    const events: AnyEvent[] = [
      {
        event_type: 'execution',
        timestamp: timestamp(0),
        lifecycle_stage: 'start',
        details: { path: 'examples/complex-workflow.tac' },
      } as ExecutionEvent,
      {
        event_type: 'log',
        timestamp: timestamp(100),
        level: 'INFO',
        message: 'Starting validation...',
      } as LogEvent,
      {
        event_type: 'log',
        timestamp: timestamp(200),
        level: 'INFO',
        message: 'Parsing Lua syntax...',
      } as LogEvent,
    ];
    
    return <ResultsSidebar events={events} isRunning={true} onClear={() => console.log('Clear clicked')} />;
  },
};
