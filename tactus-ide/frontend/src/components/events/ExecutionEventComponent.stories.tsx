import type { Meta, StoryObj } from '@storybook/react';
import { ExecutionEventComponent } from './ExecutionEventComponent';
import { ExecutionEvent } from '@/types/events';

const meta = {
  title: 'Events/ExecutionEventComponent',
  component: ExecutionEventComponent,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof ExecutionEventComponent>;

export default meta;
type Story = StoryObj<typeof meta>;

const baseTimestamp = new Date().toISOString();

export const Started: Story = {
  args: {
    event: {
      event_type: 'execution',
      timestamp: baseTimestamp,
      lifecycle_stage: 'start',
    } as ExecutionEvent,
  },
};

export const StartedWithPath: Story = {
  args: {
    event: {
      event_type: 'execution',
      timestamp: baseTimestamp,
      lifecycle_stage: 'start',
      details: {
        path: 'examples/simple-agent.tac',
      },
    } as ExecutionEvent,
  },
};

export const Completed: Story = {
  args: {
    event: {
      event_type: 'execution',
      timestamp: baseTimestamp,
      lifecycle_stage: 'complete',
      exit_code: 0,
    } as ExecutionEvent,
  },
};

export const CompletedWithDetails: Story = {
  args: {
    event: {
      event_type: 'execution',
      timestamp: baseTimestamp,
      lifecycle_stage: 'complete',
      exit_code: 0,
      details: {
        path: 'examples/complex-workflow.tac',
        duration_ms: 5432,
      },
    } as ExecutionEvent,
  },
};

export const Failed: Story = {
  args: {
    event: {
      event_type: 'execution',
      timestamp: baseTimestamp,
      lifecycle_stage: 'error',
      exit_code: 1,
    } as ExecutionEvent,
  },
};

export const FailedWithError: Story = {
  args: {
    event: {
      event_type: 'execution',
      timestamp: baseTimestamp,
      lifecycle_stage: 'error',
      exit_code: 1,
      details: {
        error: 'RuntimeError: Agent failed to initialize - missing required configuration',
        path: 'examples/broken-agent.tac',
      },
    } as ExecutionEvent,
  },
};

export const Waiting: Story = {
  args: {
    event: {
      event_type: 'execution',
      timestamp: baseTimestamp,
      lifecycle_stage: 'waiting',
      details: {
        message: 'Waiting for user input...',
      },
    } as ExecutionEvent,
  },
};
