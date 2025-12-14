import type { Meta, StoryObj } from '@storybook/react';
import { ExecutionSummaryEventComponent } from './ExecutionSummaryEventComponent';
import { ExecutionSummaryEvent, CostEvent } from '@/types/events';

const meta = {
  title: 'Events/ExecutionSummaryEventComponent',
  component: ExecutionSummaryEventComponent,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof ExecutionSummaryEventComponent>;

export default meta;
type Story = StoryObj<typeof meta>;

const baseTimestamp = new Date().toISOString();

export const SimpleExecution: Story = {
  args: {
    event: {
      event_type: 'execution_summary',
      timestamp: baseTimestamp,
      result: { status: 'success', message: 'Task completed successfully' },
      final_state: { counter: 5, processed: true },
      iterations: 1,
      tools_used: ['done'],
      total_cost: 0.03,
      total_tokens: 2000,
      cost_breakdown: [],
    } as ExecutionSummaryEvent,
  },
};

export const MultipleIterations: Story = {
  args: {
    event: {
      event_type: 'execution_summary',
      timestamp: baseTimestamp,
      result: { 
        status: 'success', 
        data: { processed: 10, failed: 0 },
        summary: 'Processed all items successfully'
      },
      final_state: { 
        items_processed: 10,
        errors: [],
        completed_at: baseTimestamp
      },
      iterations: 5,
      tools_used: ['fetch_data', 'process_item', 'save_result', 'done'],
      total_cost: 0.15,
      total_tokens: 10000,
      cost_breakdown: [],
    } as ExecutionSummaryEvent,
  },
};

export const WithCostBreakdown: Story = {
  args: {
    event: {
      event_type: 'execution_summary',
      timestamp: baseTimestamp,
      result: { status: 'success' },
      final_state: { completed: true },
      iterations: 3,
      tools_used: ['analyze', 'summarize', 'done'],
      total_cost: 0.25,
      total_tokens: 15000,
      cost_breakdown: [
        {
          event_type: 'cost',
          timestamp: baseTimestamp,
          agent_name: 'analyzer',
          model: 'gpt-4o',
          provider: 'openai',
          prompt_tokens: 5000,
          completion_tokens: 1500,
          total_tokens: 6500,
          prompt_cost: 0.05,
          completion_cost: 0.045,
          total_cost: 0.095,
          retry_count: 0,
          validation_errors: [],
          cache_hit: false,
          message_count: 2,
          new_message_count: 1,
          duration_ms: 3500,
        } as CostEvent,
        {
          event_type: 'cost',
          timestamp: baseTimestamp,
          agent_name: 'summarizer',
          model: 'gpt-4o',
          provider: 'openai',
          prompt_tokens: 6000,
          completion_tokens: 2500,
          total_tokens: 8500,
          prompt_cost: 0.06,
          completion_cost: 0.075,
          total_cost: 0.135,
          retry_count: 1,
          validation_errors: ['Format error'],
          cache_hit: false,
          message_count: 3,
          new_message_count: 2,
          duration_ms: 5200,
        } as CostEvent,
      ],
    } as ExecutionSummaryEvent,
  },
};

export const ComplexResult: Story = {
  args: {
    event: {
      event_type: 'execution_summary',
      timestamp: baseTimestamp,
      result: {
        status: 'success',
        analysis: {
          sentiment: 'positive',
          confidence: 0.95,
          topics: ['technology', 'innovation', 'future'],
        },
        recommendations: [
          'Focus on emerging technologies',
          'Invest in AI research',
          'Build strategic partnerships',
        ],
      },
      final_state: {
        documents_analyzed: 50,
        insights_generated: 12,
        processing_time_ms: 45000,
      },
      iterations: 8,
      tools_used: ['fetch_documents', 'analyze_sentiment', 'extract_topics', 'generate_recommendations', 'done'],
      total_cost: 0.45,
      total_tokens: 25000,
      cost_breakdown: [],
    } as ExecutionSummaryEvent,
  },
};
