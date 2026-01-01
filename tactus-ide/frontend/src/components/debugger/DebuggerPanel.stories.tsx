import type { Meta, StoryObj } from '@storybook/react';
import { DebuggerPanel } from './DebuggerPanel';

const meta = {
  title: 'Debugger/DebuggerPanel',
  component: DebuggerPanel,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof DebuggerPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

// Mock fetch for stories
const mockFetch = (data: any) => {
  global.fetch = jest.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(data),
    })
  ) as jest.Mock;
};

export const Default: Story = {
  args: {},
  beforeEach: () => {
    mockFetch({
      runs: [
        {
          run_id: 'run-abc-123',
          procedure_name: 'customer_support',
          file_path: '/procedures/customer_support.tac',
          start_time: new Date(Date.now() - 3600000).toISOString(),
          end_time: new Date().toISOString(),
          status: 'COMPLETED',
          checkpoint_count: 15,
        },
        {
          run_id: 'run-def-456',
          procedure_name: 'data_processing',
          file_path: '/procedures/data_processing.tac',
          start_time: new Date(Date.now() - 7200000).toISOString(),
          status: 'RUNNING',
          checkpoint_count: 8,
        },
      ],
    });
  },
};

export const WithSelectedRun: Story = {
  args: {
    initialRunId: 'run-abc-123',
  },
};

export const WithCloseButton: Story = {
  args: {
    onClose: () => alert('Close clicked'),
  },
};
