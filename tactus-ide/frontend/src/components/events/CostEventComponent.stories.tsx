import type { Meta, StoryObj } from '@storybook/react';
import { CostEventComponent } from './CostEventComponent';
import { CostEvent } from '@/types/events';

const meta = {
  title: 'Events/CostEventComponent',
  component: CostEventComponent,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof CostEventComponent>;

export default meta;
type Story = StoryObj<typeof meta>;

const baseTimestamp = new Date().toISOString();

export const BasicCost: Story = {
  args: {
    event: {
      event_type: 'cost',
      timestamp: baseTimestamp,
      agent_name: 'my_agent',
      model: 'gpt-4o',
      provider: 'openai',
      prompt_tokens: 1500,
      completion_tokens: 500,
      total_tokens: 2000,
      prompt_cost: 0.015,
      completion_cost: 0.015,
      total_cost: 0.03,
      retry_count: 0,
      validation_errors: [],
      cache_hit: false,
      message_count: 3,
      new_message_count: 1,
      duration_ms: 2500,
    } as CostEvent,
  },
};

export const WithRetries: Story = {
  args: {
    event: {
      event_type: 'cost',
      timestamp: baseTimestamp,
      agent_name: 'my_agent',
      model: 'gpt-4o',
      provider: 'openai',
      prompt_tokens: 2500,
      completion_tokens: 800,
      total_tokens: 3300,
      prompt_cost: 0.025,
      completion_cost: 0.024,
      total_cost: 0.049,
      retry_count: 3,
      validation_errors: ['Invalid JSON format', 'Missing required field', 'Type mismatch'],
      cache_hit: false,
      message_count: 5,
      new_message_count: 2,
      duration_ms: 8500,
    } as CostEvent,
  },
};

export const WithCacheHit: Story = {
  args: {
    event: {
      event_type: 'cost',
      timestamp: baseTimestamp,
      agent_name: 'cached_agent',
      model: 'gpt-4o-mini',
      provider: 'openai',
      prompt_tokens: 1000,
      completion_tokens: 300,
      total_tokens: 1300,
      prompt_cost: 0.005,
      completion_cost: 0.003,
      total_cost: 0.008,
      retry_count: 0,
      validation_errors: [],
      cache_hit: true,
      cache_tokens: 800,
      cache_cost: 0.004,
      message_count: 2,
      new_message_count: 1,
      duration_ms: 1200,
    } as CostEvent,
  },
};

export const ExpensiveCall: Story = {
  args: {
    event: {
      event_type: 'cost',
      timestamp: baseTimestamp,
      agent_name: 'complex_agent',
      model: 'claude-3-5-sonnet-20240620',
      provider: 'bedrock',
      prompt_tokens: 15000,
      completion_tokens: 5000,
      total_tokens: 20000,
      prompt_cost: 0.15,
      completion_cost: 0.15,
      total_cost: 0.30,
      retry_count: 1,
      validation_errors: ['Schema validation failed'],
      cache_hit: false,
      message_count: 10,
      new_message_count: 3,
      duration_ms: 15000,
      latency_ms: 500,
      temperature: 0.7,
      max_tokens: 8000,
      request_id: 'req_abc123xyz',
    } as CostEvent,
  },
};
