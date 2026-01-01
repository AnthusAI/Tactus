import type { Meta, StoryObj } from '@storybook/react';
import { RunSelector } from './RunSelector';
import type { RunListItem } from '../../types/tracing';

const meta = {
  title: 'Debugger/RunSelector',
  component: RunSelector,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof RunSelector>;

export default meta;
type Story = StoryObj<typeof meta>;

const mockRuns: RunListItem[] = [
  {
    run_id: 'run-abc-123',
    procedure_name: 'customer_support',
    file_path: '/procedures/customer_support.tac',
    start_time: new Date(Date.now() - 300000).toISOString(), // 5 minutes ago
    end_time: new Date(Date.now() - 60000).toISOString(),
    status: 'COMPLETED',
    checkpoint_count: 15,
  },
  {
    run_id: 'run-def-456',
    procedure_name: 'data_processing',
    file_path: '/procedures/data_processing.tac',
    start_time: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
    status: 'RUNNING',
    checkpoint_count: 8,
  },
  {
    run_id: 'run-ghi-789',
    procedure_name: 'batch_job',
    file_path: '/procedures/batch_job.tac',
    start_time: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
    end_time: new Date(Date.now() - 86000000).toISOString(),
    status: 'FAILED',
    checkpoint_count: 42,
  },
  {
    run_id: 'run-jkl-012',
    procedure_name: 'review_workflow',
    file_path: '/procedures/review_workflow.tac',
    start_time: new Date(Date.now() - 180000).toISOString(), // 3 minutes ago
    status: 'PAUSED',
    checkpoint_count: 5,
  },
  {
    run_id: 'run-mno-345',
    procedure_name: 'customer_support',
    file_path: '/procedures/customer_support.tac',
    start_time: new Date(Date.now() - 604800000).toISOString(), // 1 week ago
    end_time: new Date(Date.now() - 604000000).toISOString(),
    status: 'COMPLETED',
    checkpoint_count: 23,
  },
];

export const Default: Story = {
  args: {
    runs: mockRuns,
    selectedRunId: null,
    onSelect: (runId: string) => console.log('Selected run:', runId),
  },
};

export const WithSelection: Story = {
  args: {
    runs: mockRuns,
    selectedRunId: 'run-abc-123',
    onSelect: (runId: string) => console.log('Selected run:', runId),
  },
};

export const Loading: Story = {
  args: {
    runs: [],
    selectedRunId: null,
    onSelect: (runId: string) => console.log('Selected run:', runId),
    loading: true,
  },
};

export const Empty: Story = {
  args: {
    runs: [],
    selectedRunId: null,
    onSelect: (runId: string) => console.log('Selected run:', runId),
    loading: false,
  },
};

export const RunningRun: Story = {
  args: {
    runs: mockRuns,
    selectedRunId: 'run-def-456',
    onSelect: (runId: string) => console.log('Selected run:', runId),
  },
};

export const FailedRun: Story = {
  args: {
    runs: mockRuns,
    selectedRunId: 'run-ghi-789',
    onSelect: (runId: string) => console.log('Selected run:', runId),
  },
};

export const PausedRun: Story = {
  args: {
    runs: mockRuns,
    selectedRunId: 'run-jkl-012',
    onSelect: (runId: string) => console.log('Selected run:', runId),
  },
};
