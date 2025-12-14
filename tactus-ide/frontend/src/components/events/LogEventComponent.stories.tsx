import type { Meta, StoryObj } from '@storybook/react';
import { LogEventComponent } from './LogEventComponent';
import { LogEvent } from '@/types/events';

const meta = {
  title: 'Events/LogEventComponent',
  component: LogEventComponent,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof LogEventComponent>;

export default meta;
type Story = StoryObj<typeof meta>;

const baseTimestamp = new Date().toISOString();

export const Debug: Story = {
  args: {
    event: {
      event_type: 'log',
      timestamp: baseTimestamp,
      level: 'DEBUG',
      message: 'Debugging information for development',
    } as LogEvent,
  },
};

export const Info: Story = {
  args: {
    event: {
      event_type: 'log',
      timestamp: baseTimestamp,
      level: 'INFO',
      message: 'Application started successfully',
    } as LogEvent,
  },
};

export const Warning: Story = {
  args: {
    event: {
      event_type: 'log',
      timestamp: baseTimestamp,
      level: 'WARNING',
      message: 'This operation may take longer than expected',
    } as LogEvent,
  },
};

export const Error: Story = {
  args: {
    event: {
      event_type: 'log',
      timestamp: baseTimestamp,
      level: 'ERROR',
      message: 'Failed to connect to database',
    } as LogEvent,
  },
};

export const Critical: Story = {
  args: {
    event: {
      event_type: 'log',
      timestamp: baseTimestamp,
      level: 'CRITICAL',
      message: 'System failure - immediate attention required',
    } as LogEvent,
  },
};

export const WithContext: Story = {
  args: {
    event: {
      event_type: 'log',
      timestamp: baseTimestamp,
      level: 'ERROR',
      message: 'API request failed',
      context: {
        endpoint: '/api/users',
        method: 'GET',
        status_code: 500,
        error: 'Internal Server Error',
        retry_count: 3,
      },
    } as LogEvent,
  },
};

export const WithComplexContext: Story = {
  args: {
    event: {
      event_type: 'log',
      timestamp: baseTimestamp,
      level: 'INFO',
      message: 'User authentication successful',
      context: {
        user_id: '12345',
        username: 'john.doe',
        roles: ['admin', 'developer'],
        session: {
          id: 'sess_abc123',
          created_at: '2024-01-15T10:30:00Z',
          expires_at: '2024-01-15T18:30:00Z',
        },
        metadata: {
          ip_address: '192.168.1.100',
          user_agent: 'Mozilla/5.0',
        },
      },
      logger_name: 'auth.service',
    } as LogEvent,
  },
};

export const LongMessage: Story = {
  args: {
    event: {
      event_type: 'log',
      timestamp: baseTimestamp,
      level: 'WARNING',
      message: 'This is a very long log message that demonstrates how the component handles text wrapping and layout when the message content exceeds the normal width of the container. It should wrap properly and maintain readability.',
    } as LogEvent,
  },
};
