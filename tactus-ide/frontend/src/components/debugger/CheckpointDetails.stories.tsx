import type { Meta, StoryObj } from '@storybook/react';
import { CheckpointDetails } from './CheckpointDetails';
import type { CheckpointEntry } from '../../types/tracing';

const meta = {
  title: 'Debugger/CheckpointDetails',
  component: CheckpointDetails,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof CheckpointDetails>;

export default meta;
type Story = StoryObj<typeof meta>;

const mockCheckpoint: CheckpointEntry = {
  position: 5,
  type: 'agent_turn',
  result: {
    text: 'Based on your request, I recommend the premium plan.',
    confidence: 0.87,
    reasoning: 'User mentioned enterprise features',
  },
  timestamp: new Date().toISOString(),
  duration_ms: 234.5,
  source_location: {
    file: '/procedures/customer_support.tac',
    line: 42,
    function: 'recommend_plan',
    code_context: `local function recommend_plan(state)
  local features = state.requested_features
  return Agent({message = "Recommend based on " .. features})
end`,
  },
  captured_vars: {
    state: {
      user_id: 'user-123',
      requested_features: ['SSO', 'Advanced Analytics', 'API Access'],
      conversation_history: [
        { role: 'user', text: 'I need enterprise features' },
        { role: 'agent', text: 'Let me help you with that' },
      ],
    },
    current_plan: 'basic',
    upgrade_available: true,
  },
};

const mockCheckpointWithoutSource: CheckpointEntry = {
  position: 3,
  type: 'model_predict',
  result: {
    prediction: 'intent_upgrade',
    confidence: 0.92,
  },
  timestamp: new Date().toISOString(),
  duration_ms: 450.2,
};

const mockCheckpointWithLargeData: CheckpointEntry = {
  position: 10,
  type: 'step',
  result: {
    processed_items: Array.from({ length: 20 }, (_, i) => ({
      id: `item-${i}`,
      name: `Product ${i}`,
      price: 100 + i * 10,
      category: ['electronics', 'clothing', 'books'][i % 3],
      in_stock: i % 2 === 0,
    })),
    total_count: 20,
    processing_time: 1234,
  },
  timestamp: new Date().toISOString(),
  duration_ms: 1234.5,
  source_location: {
    file: '/procedures/batch_processing.tac',
    line: 78,
    function: 'process_batch',
  },
  captured_vars: {
    batch_size: 20,
    current_batch: 3,
    total_batches: 10,
    errors: [],
  },
};

export const Default: Story = {
  args: {
    checkpoint: mockCheckpoint,
  },
};

export const WithoutSourceLocation: Story = {
  args: {
    checkpoint: mockCheckpointWithoutSource,
  },
};

export const WithLargeData: Story = {
  args: {
    checkpoint: mockCheckpointWithLargeData,
  },
};

export const ModelPredictCheckpoint: Story = {
  args: {
    checkpoint: {
      position: 8,
      type: 'model_predict',
      result: {
        model: 'gpt-4',
        prediction: {
          intent: 'product_inquiry',
          entities: {
            product: 'laptop',
            price_range: '1000-1500',
          },
          confidence: 0.94,
        },
      },
      timestamp: new Date().toISOString(),
      duration_ms: 1250.8,
      source_location: {
        file: '/procedures/nlp.tac',
        line: 156,
        function: 'extract_intent',
        code_context: `local function extract_intent(text)
  local result = Model.predict({
    prompt = "Extract intent from: " .. text,
    model = "gpt-4"
  })
  return result
end`,
      },
    },
  },
};

export const HumanInputCheckpoint: Story = {
  args: {
    checkpoint: {
      position: 12,
      type: 'human_input',
      result: {
        approved: true,
        feedback: 'The classification looks accurate',
        reviewer: 'john@example.com',
        review_time_seconds: 45,
      },
      timestamp: new Date().toISOString(),
      duration_ms: 45000.0,
      source_location: {
        file: '/procedures/review.tac',
        line: 89,
        function: 'request_human_review',
      },
      captured_vars: {
        pending_review: true,
        reviewer_queue: ['john@example.com', 'jane@example.com'],
        priority: 'high',
      },
    },
  },
};
