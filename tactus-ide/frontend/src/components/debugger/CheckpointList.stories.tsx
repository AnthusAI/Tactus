import type { Meta, StoryObj } from '@storybook/react';
import { CheckpointList } from './CheckpointList';
import type { CheckpointEntry } from '../../types/tracing';

const meta = {
  title: 'Debugger/CheckpointList',
  component: CheckpointList,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof CheckpointList>;

export default meta;
type Story = StoryObj<typeof meta>;

const mockCheckpoints: CheckpointEntry[] = [
  {
    position: 0,
    type: 'agent_turn',
    result: { text: 'Hello, how can I help you?' },
    timestamp: new Date(Date.now() - 10000).toISOString(),
    duration_ms: 125.5,
    source_location: {
      file: '/procedures/customer_support.tac',
      line: 15,
      function: 'handle_greeting',
    },
  },
  {
    position: 1,
    type: 'model_predict',
    result: { prediction: 'intent_greeting', confidence: 0.95 },
    timestamp: new Date(Date.now() - 8000).toISOString(),
    duration_ms: 450.2,
    source_location: {
      file: '/procedures/customer_support.tac',
      line: 23,
      function: 'classify_intent',
    },
  },
  {
    position: 2,
    type: 'human_input',
    result: { approved: true, feedback: 'Looks good' },
    timestamp: new Date(Date.now() - 5000).toISOString(),
    duration_ms: 2500.0,
    source_location: {
      file: '/procedures/customer_support.tac',
      line: 35,
      function: 'request_approval',
    },
  },
  {
    position: 3,
    type: 'step',
    result: { status: 'processed' },
    timestamp: new Date(Date.now() - 2000).toISOString(),
    duration_ms: 50.1,
    source_location: {
      file: '/procedures/customer_support.tac',
      line: 42,
      function: 'finalize',
    },
  },
  {
    position: 4,
    type: 'agent_turn',
    result: { text: 'Thank you! Is there anything else?' },
    timestamp: new Date().toISOString(),
    duration_ms: 180.3,
    source_location: {
      file: '/procedures/customer_support.tac',
      line: 50,
      function: 'handle_followup',
    },
  },
];

export const Default: Story = {
  args: {
    checkpoints: mockCheckpoints,
    selectedPosition: null,
    onSelect: (position: number) => console.log('Selected checkpoint:', position),
  },
};

export const WithSelection: Story = {
  args: {
    checkpoints: mockCheckpoints,
    selectedPosition: 2,
    onSelect: (position: number) => console.log('Selected checkpoint:', position),
  },
};

export const Empty: Story = {
  args: {
    checkpoints: [],
    selectedPosition: null,
    onSelect: (position: number) => console.log('Selected checkpoint:', position),
  },
};

export const ManyCheckpoints: Story = {
  args: {
    checkpoints: Array.from({ length: 50 }, (_, i) => ({
      position: i,
      type: ['agent_turn', 'model_predict', 'human_input', 'step'][i % 4],
      result: { data: `Result ${i}` },
      timestamp: new Date(Date.now() - (50 - i) * 1000).toISOString(),
      duration_ms: Math.random() * 1000,
      source_location: {
        file: '/procedures/test.tac',
        line: 10 + i,
        function: `function_${i}`,
      },
    })),
    selectedPosition: 25,
    onSelect: (position: number) => console.log('Selected checkpoint:', position),
  },
};
