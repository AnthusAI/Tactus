import type { Meta, StoryObj } from '@storybook/react';
import { ProcedureInputsModal } from './ProcedureInputsModal';
import { useState } from 'react';
import { ParameterDeclaration } from '@/types/metadata';

const meta = {
  title: 'Components/ProcedureInputsModal',
  component: ProcedureInputsModal,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof ProcedureInputsModal>;

export default meta;
type Story = StoryObj<typeof meta>;

// Wrapper component to manage modal state in stories
const ModalWrapper = ({ parameters }: { parameters: Record<string, ParameterDeclaration> }) => {
  const [open, setOpen] = useState(true);
  const [lastSubmit, setLastSubmit] = useState<Record<string, any> | null>(null);

  return (
    <div className="min-h-[400px] min-w-[600px] p-4">
      {lastSubmit && (
        <div className="mb-4 p-4 bg-muted rounded-md">
          <h4 className="text-sm font-semibold mb-2">Last submitted values:</h4>
          <pre className="text-xs">{JSON.stringify(lastSubmit, null, 2)}</pre>
        </div>
      )}
      <button
        onClick={() => setOpen(true)}
        className="px-4 py-2 bg-primary text-primary-foreground rounded-md"
      >
        Open Modal
      </button>
      <ProcedureInputsModal
        open={open}
        onOpenChange={setOpen}
        parameters={parameters}
        onSubmit={(values) => {
          setLastSubmit(values);
          setOpen(false);
        }}
        onCancel={() => setOpen(false)}
      />
    </div>
  );
};

export const StringInput: Story = {
  render: () => (
    <ModalWrapper
      parameters={{
        name: {
          name: 'name',
          type: 'string',
          required: true,
          description: 'User name to greet',
        },
      }}
    />
  ),
};

export const AllTypes: Story = {
  render: () => (
    <ModalWrapper
      parameters={{
        name: {
          name: 'name',
          type: 'string',
          required: true,
          description: 'Your name',
        },
        age: {
          name: 'age',
          type: 'number',
          required: false,
          default: 25,
          description: 'Your age in years',
        },
        active: {
          name: 'active',
          type: 'boolean',
          required: false,
          default: true,
          description: 'Whether the user is active',
        },
        tags: {
          name: 'tags',
          type: 'array',
          required: false,
          default: ['tag1', 'tag2'],
          description: 'List of tags',
        },
        config: {
          name: 'config',
          type: 'object',
          required: false,
          default: { key: 'value' },
          description: 'Configuration object',
        },
      }}
    />
  ),
};

export const WithEnumField: Story = {
  render: () => (
    <ModalWrapper
      parameters={{
        status: {
          name: 'status',
          type: 'string',
          required: true,
          enum: ['active', 'inactive', 'pending'],
          description: 'Current status',
        },
        priority: {
          name: 'priority',
          type: 'string',
          required: false,
          default: 'medium',
          enum: ['low', 'medium', 'high', 'critical'],
          description: 'Priority level',
        },
      }}
    />
  ),
};

export const ArrayOfNumbers: Story = {
  render: () => (
    <ModalWrapper
      parameters={{
        numbers: {
          name: 'numbers',
          type: 'array',
          required: true,
          description: 'Array of numbers to process (e.g., [1, 2, 3, 4, 5])',
        },
      }}
    />
  ),
};

export const ComplexForm: Story = {
  render: () => (
    <ModalWrapper
      parameters={{
        user_name: {
          name: 'user_name',
          type: 'string',
          required: true,
          description: 'Your name for personalization',
        },
        repeat_count: {
          name: 'repeat_count',
          type: 'number',
          default: 3,
          required: false,
          description: 'Number of times to repeat the greeting',
        },
        formal: {
          name: 'formal',
          type: 'boolean',
          default: false,
          required: false,
          description: 'Use formal greeting style',
        },
        topics: {
          name: 'topics',
          type: 'array',
          default: [],
          required: false,
          description: 'List of topics to mention',
        },
        preferences: {
          name: 'preferences',
          type: 'object',
          default: {},
          required: false,
          description: 'User preferences as JSON object',
        },
        language: {
          name: 'language',
          type: 'string',
          default: 'english',
          required: false,
          enum: ['english', 'spanish', 'french', 'german'],
          description: 'Language for the greeting',
        },
      }}
    />
  ),
};

export const RequiredFieldsOnly: Story = {
  render: () => (
    <ModalWrapper
      parameters={{
        api_key: {
          name: 'api_key',
          type: 'string',
          required: true,
          description: 'Your API key (required)',
        },
        endpoint: {
          name: 'endpoint',
          type: 'string',
          required: true,
          description: 'API endpoint URL',
        },
        max_retries: {
          name: 'max_retries',
          type: 'number',
          required: true,
          description: 'Maximum number of retries',
        },
      }}
    />
  ),
};

export const WithDefaults: Story = {
  render: () => (
    <ModalWrapper
      parameters={{
        timeout: {
          name: 'timeout',
          type: 'number',
          required: false,
          default: 30,
          description: 'Request timeout in seconds',
        },
        debug: {
          name: 'debug',
          type: 'boolean',
          required: false,
          default: false,
          description: 'Enable debug logging',
        },
        headers: {
          name: 'headers',
          type: 'object',
          required: false,
          default: { 'Content-Type': 'application/json' },
          description: 'HTTP headers to include',
        },
      }}
    />
  ),
};
