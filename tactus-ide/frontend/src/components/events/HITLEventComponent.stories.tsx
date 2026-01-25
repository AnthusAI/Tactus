import type { Meta, StoryObj } from '@storybook/react';
import { HITLEventComponent } from './HITLEventComponent';
import { HITLRequestEvent } from '@/types/events';

const meta = {
  title: 'Events/HITLEventComponent',
  component: HITLEventComponent,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
  argTypes: {
    displayMode: {
      control: 'radio',
      options: ['inline', 'standalone'],
      description: 'Display mode: inline (context hidden) or standalone (context shown)',
    },
  },
} satisfies Meta<typeof HITLEventComponent>;

export default meta;
type Story = StoryObj<typeof meta>;

const baseTimestamp = new Date().toISOString();

// Base event for reuse
const baseEvent: HITLRequestEvent = {
  event_type: 'hitl.request',
  timestamp: baseTimestamp,
  request_id: 'req-001',
  procedure_name: 'deploy-workflow',
  invocation_id: 'inv-12345',
  request_type: 'approval',
  message: 'Deploy v1.0.0 to production?',
};

// ===== INLINE MODE STORIES =====

export const InlineApproval: Story = {
  name: 'Inline - Approval Request',
  args: {
    event: {
      ...baseEvent,
      request_type: 'approval',
      message: 'Deploy v1.0.0 to production?',
    },
    displayMode: 'inline',
  },
};

export const InlineApprovalWithOptions: Story = {
  name: 'Inline - Approval with Custom Options',
  args: {
    event: {
      ...baseEvent,
      request_type: 'approval',
      message: 'How would you like to proceed with the deployment?',
      options: [
        { label: 'Deploy Now', value: 'deploy', style: 'primary' },
        { label: 'Schedule for Later', value: 'schedule', style: 'secondary' },
        { label: 'Cancel', value: 'cancel', style: 'danger' },
      ],
    },
    displayMode: 'inline',
  },
};

export const InlineInput: Story = {
  name: 'Inline - Text Input',
  args: {
    event: {
      ...baseEvent,
      request_type: 'input',
      message: 'Please provide a reason for the deployment:',
    },
    displayMode: 'inline',
  },
};

export const InlineSelect: Story = {
  name: 'Inline - Select Options',
  args: {
    event: {
      ...baseEvent,
      request_type: 'select',
      message: 'Select the target environment:',
      options: [
        { label: 'Development', value: 'dev' },
        { label: 'Staging', value: 'staging' },
        { label: 'Production', value: 'prod' },
      ],
    },
    displayMode: 'inline',
  },
};

// ===== STANDALONE MODE STORIES =====

export const StandaloneWithRuntimeContext: Story = {
  name: 'Standalone - With Runtime Context',
  args: {
    event: {
      ...baseEvent,
      request_type: 'approval',
      message: 'Deploy v1.0.0 to production?',
      runtime_context: {
        source_line: 42,
        source_file: 'examples/deploy-workflow.tac',
        checkpoint_position: 5,
        procedure_name: 'deploy-workflow',
        invocation_id: 'inv-12345',
        started_at: new Date(Date.now() - 150000).toISOString(), // 2.5 minutes ago
        elapsed_seconds: 150,
        backtrace: [
          { checkpoint_type: 'procedure_start', line: 10, function_name: 'main' },
          { checkpoint_type: 'llm_call', line: 25, duration_ms: 2500 },
          { checkpoint_type: 'tool_call', line: 35, function_name: 'check_status', duration_ms: 500 },
          { checkpoint_type: 'hitl_approval', line: 42 },
        ],
      },
    },
    displayMode: 'standalone',
  },
};

export const StandaloneWithApplicationContext: Story = {
  name: 'Standalone - With Application Context',
  args: {
    event: {
      ...baseEvent,
      request_type: 'approval',
      message: 'Approve the escalation for this support ticket?',
      application_context: [
        { name: 'Evaluation', value: 'Monthly QA Review', url: '/evaluations/123' },
        { name: 'Scorecard', value: 'Customer Support Quality', url: '/scorecards/456' },
        { name: 'Customer', value: 'Acme Corp', url: '/customers/acme' },
      ],
    },
    displayMode: 'standalone',
  },
};

export const StandaloneWithFullContext: Story = {
  name: 'Standalone - Full Context (Runtime + Application)',
  args: {
    event: {
      ...baseEvent,
      request_type: 'approval',
      message: 'Deploy v2.1.0 to production environment?',
      subject: 'Production Deployment Request',
      runtime_context: {
        source_line: 78,
        source_file: 'procedures/deploy.tac',
        checkpoint_position: 12,
        procedure_name: 'production-deploy',
        invocation_id: 'inv-98765',
        started_at: new Date(Date.now() - 300000).toISOString(), // 5 minutes ago
        elapsed_seconds: 300,
        backtrace: [
          { checkpoint_type: 'procedure_start', line: 1 },
          { checkpoint_type: 'llm_call', line: 15, duration_ms: 3200 },
          { checkpoint_type: 'tool_call', line: 30, function_name: 'validate_config', duration_ms: 150 },
          { checkpoint_type: 'tool_call', line: 45, function_name: 'run_tests', duration_ms: 45000 },
          { checkpoint_type: 'llm_call', line: 60, duration_ms: 2800 },
          { checkpoint_type: 'hitl_approval', line: 78 },
        ],
      },
      application_context: [
        { name: 'Release', value: 'v2.1.0', url: '/releases/v2.1.0' },
        { name: 'Environment', value: 'Production', url: '/environments/prod' },
        { name: 'Deployment', value: 'Deploy #1234', url: '/deployments/1234' },
        { name: 'Requested By', value: 'Alice Johnson' },
      ],
    },
    displayMode: 'standalone',
  },
};

export const StandaloneInputWithContext: Story = {
  name: 'Standalone - Input with Context',
  args: {
    event: {
      ...baseEvent,
      request_type: 'input',
      message: 'Please provide feedback for this agent response:',
      runtime_context: {
        source_line: 55,
        source_file: 'evaluations/qa-review.tac',
        checkpoint_position: 8,
        procedure_name: 'qa-review',
        invocation_id: 'inv-55555',
        elapsed_seconds: 45,
        backtrace: [],
      },
      application_context: [
        { name: 'Agent', value: 'Support Triage Bot', url: '/agents/support-triage' },
        { name: 'Conversation', value: '#conv-789', url: '/conversations/789' },
      ],
    },
    displayMode: 'standalone',
  },
};

export const StandaloneSelectWithContext: Story = {
  name: 'Standalone - Select with Context',
  args: {
    event: {
      ...baseEvent,
      request_type: 'select',
      message: 'Rate the quality of this agent response:',
      options: [
        { label: 'Excellent', value: 5 },
        { label: 'Good', value: 4 },
        { label: 'Acceptable', value: 3 },
        { label: 'Poor', value: 2 },
        { label: 'Unacceptable', value: 1 },
      ],
      runtime_context: {
        source_line: 120,
        checkpoint_position: 15,
        procedure_name: 'agent-evaluation',
        invocation_id: 'inv-eval-001',
        elapsed_seconds: 180,
        backtrace: [],
      },
      application_context: [
        { name: 'Evaluation', value: 'Weekly QA' },
        { name: 'Agent', value: 'Customer Success Bot' },
      ],
    },
    displayMode: 'standalone',
  },
};

// ===== EDGE CASES =====

export const StandaloneWithLongElapsedTime: Story = {
  name: 'Standalone - Long Elapsed Time',
  args: {
    event: {
      ...baseEvent,
      request_type: 'approval',
      message: 'Continue processing after long wait?',
      runtime_context: {
        checkpoint_position: 50,
        procedure_name: 'batch-processor',
        invocation_id: 'inv-batch-001',
        elapsed_seconds: 7350, // 2 hours, 2 minutes, 30 seconds
        backtrace: [],
      },
    },
    displayMode: 'standalone',
  },
};

export const StandaloneMinimalContext: Story = {
  name: 'Standalone - Minimal Runtime Context',
  args: {
    event: {
      ...baseEvent,
      request_type: 'approval',
      message: 'Proceed with operation?',
      runtime_context: {
        checkpoint_position: 1,
        procedure_name: 'simple-workflow',
        invocation_id: 'inv-simple',
        elapsed_seconds: 0,
        backtrace: [],
      },
    },
    displayMode: 'standalone',
  },
};

// ===== COMPARISON STORIES =====

export const InlineWithRuntimeContext: Story = {
  name: 'Inline - With Runtime Context',
  args: {
    event: {
      ...baseEvent,
      request_type: 'approval',
      message: 'Deploy v1.0.0 to production?',
      runtime_context: {
        source_line: 42,
        source_file: 'examples/deploy.tac',
        checkpoint_position: 5,
        procedure_name: 'deploy',
        invocation_id: 'inv-12345',
        elapsed_seconds: 150,
        backtrace: [],
      },
      application_context: [
        { name: 'Environment', value: 'Production', url: '/env/prod' },
      ],
    },
    displayMode: 'inline',
  },
  parameters: {
    docs: {
      description: {
        story: 'In inline mode, runtime context (source line, elapsed time) is shown, but application context (domain-specific links) is hidden since it only makes sense in a unified inbox.',
      },
    },
  },
};
