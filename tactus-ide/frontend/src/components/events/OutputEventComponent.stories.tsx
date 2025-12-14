import type { Meta, StoryObj } from '@storybook/react';
import { OutputEventComponent } from './OutputEventComponent';
import { OutputEvent } from '@/types/events';

const meta = {
  title: 'Events/OutputEventComponent',
  component: OutputEventComponent,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof OutputEventComponent>;

export default meta;
type Story = StoryObj<typeof meta>;

const baseTimestamp = new Date().toISOString();

export const Stdout: Story = {
  args: {
    event: {
      event_type: 'output',
      timestamp: baseTimestamp,
      stream: 'stdout',
      content: 'Processing item 1 of 10...',
    } as OutputEvent,
  },
};

export const StdoutMultiline: Story = {
  args: {
    event: {
      event_type: 'output',
      timestamp: baseTimestamp,
      stream: 'stdout',
      content: `Starting agent execution...
Initializing tools: fetch_data, process, save
Configuration loaded successfully
Ready to process requests`,
    } as OutputEvent,
  },
};

export const Stderr: Story = {
  args: {
    event: {
      event_type: 'output',
      timestamp: baseTimestamp,
      stream: 'stderr',
      content: 'Warning: Deprecated API usage detected',
    } as OutputEvent,
  },
};

export const StderrError: Story = {
  args: {
    event: {
      event_type: 'output',
      timestamp: baseTimestamp,
      stream: 'stderr',
      content: 'ERROR: Failed to connect to database\nConnection timeout after 30 seconds',
    } as OutputEvent,
  },
};

export const StderrStackTrace: Story = {
  args: {
    event: {
      event_type: 'output',
      timestamp: baseTimestamp,
      stream: 'stderr',
      content: `Traceback (most recent call last):
  File "/app/agent.py", line 42, in execute
    result = self.process_request(data)
  File "/app/agent.py", line 78, in process_request
    return self.handler(data)
  File "/app/handlers.py", line 15, in handler
    raise ValueError("Invalid input format")
ValueError: Invalid input format`,
    } as OutputEvent,
  },
};

export const LongOutput: Story = {
  args: {
    event: {
      event_type: 'output',
      timestamp: baseTimestamp,
      stream: 'stdout',
      content: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.',
    } as OutputEvent,
  },
};

export const JSONOutput: Story = {
  args: {
    event: {
      event_type: 'output',
      timestamp: baseTimestamp,
      stream: 'stdout',
      content: JSON.stringify({
        status: 'success',
        data: {
          processed: 42,
          failed: 0,
          skipped: 3,
        },
        timestamp: '2024-01-15T10:30:00Z',
      }, null, 2),
    } as OutputEvent,
  },
};
