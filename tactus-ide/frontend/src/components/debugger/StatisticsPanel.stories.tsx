import type { Meta, StoryObj } from '@storybook/react';
import { StatisticsPanel } from './StatisticsPanel';

// Store original fetch
const originalFetch = window.fetch;

// Mock fetch implementation
const createMockFetch = (data: any) => {
  return async (url: string) => {
    console.log('Mock fetch called for:', url);
    return {
      ok: true,
      status: 200,
      json: async () => data,
    } as Response;
  };
};

const meta = {
  title: 'Debugger/StatisticsPanel',
  component: StatisticsPanel,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
  decorators: [
    (Story, context) => {
      // Install mock BEFORE rendering (synchronously)
      const mockData = context.parameters.mockData;
      if (mockData) {
        window.fetch = createMockFetch(mockData) as any;
      }

      // Render with cleanup
      try {
        return (
          <div style={{ width: '400px' }}>
            <Story />
          </div>
        );
      } finally {
        // Restore original fetch after story unmounts
        setTimeout(() => {
          window.fetch = originalFetch;
        }, 0);
      }
    },
  ],
} satisfies Meta<typeof StatisticsPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

// Mock data templates
const mockStatistics = {
  run_id: 'run-abc-123',
  procedure: 'customer_support',
  status: 'COMPLETED',
  total_checkpoints: 42,
  checkpoints_by_type: {
    agent_turn: 15,
    model_predict: 12,
    human_input: 8,
    step: 7,
  },
  total_duration_ms: 15420.5,
  has_source_locations: 38,
};

export const Default: Story = {
  args: {
    runId: 'run-abc-123',
  },
  parameters: {
    mockData: mockStatistics,
  },
};

export const RunningRun: Story = {
  args: {
    runId: 'run-def-456',
  },
  parameters: {
    mockData: {
      ...mockStatistics,
      run_id: 'run-def-456',
      status: 'RUNNING',
      total_checkpoints: 8,
      checkpoints_by_type: {
        agent_turn: 4,
        model_predict: 3,
        step: 1,
      },
      total_duration_ms: 2340.2,
      has_source_locations: 7,
    },
  },
};

export const FailedRun: Story = {
  args: {
    runId: 'run-ghi-789',
  },
  parameters: {
    mockData: {
      ...mockStatistics,
      run_id: 'run-ghi-789',
      status: 'FAILED',
      total_checkpoints: 125,
      checkpoints_by_type: {
        agent_turn: 45,
        model_predict: 38,
        human_input: 25,
        step: 17,
      },
      total_duration_ms: 125340.8,
      has_source_locations: 120,
    },
  },
};

export const LongRunningJob: Story = {
  args: {
    runId: 'run-long',
  },
  parameters: {
    mockData: {
      ...mockStatistics,
      run_id: 'run-long',
      total_checkpoints: 1500,
      checkpoints_by_type: {
        agent_turn: 500,
        model_predict: 450,
        human_input: 300,
        step: 250,
      },
      total_duration_ms: 3600000, // 1 hour
      has_source_locations: 1450,
    },
  },
};

export const MinimalCheckpoints: Story = {
  args: {
    runId: 'run-minimal',
  },
  parameters: {
    mockData: {
      ...mockStatistics,
      run_id: 'run-minimal',
      total_checkpoints: 3,
      checkpoints_by_type: {
        agent_turn: 2,
        step: 1,
      },
      total_duration_ms: 450.2,
      has_source_locations: 3,
    },
  },
};

export const NoSourceLocations: Story = {
  args: {
    runId: 'run-no-source',
  },
  parameters: {
    mockData: {
      ...mockStatistics,
      run_id: 'run-no-source',
      has_source_locations: 0,
    },
  },
};
