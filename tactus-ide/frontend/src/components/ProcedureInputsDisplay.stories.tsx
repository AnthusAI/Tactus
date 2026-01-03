import type { Meta, StoryObj } from '@storybook/react';
import { ProcedureInputsDisplay } from './ProcedureInputsDisplay';

const meta = {
  title: 'Components/ProcedureInputsDisplay',
  component: ProcedureInputsDisplay,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="w-[300px] bg-background border rounded-md">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ProcedureInputsDisplay>;

export default meta;
type Story = StoryObj<typeof meta>;

export const StringInput: Story = {
  args: {
    inputs: {
      name: 'Alice',
    },
  },
};

export const NumberInput: Story = {
  args: {
    inputs: {
      count: 42,
      ratio: 3.14159,
    },
  },
};

export const BooleanInputs: Story = {
  args: {
    inputs: {
      enabled: true,
      debug: false,
    },
  },
};

export const ArrayInput: Story = {
  args: {
    inputs: {
      numbers: [1, 2, 3, 4, 5],
      tags: ['react', 'typescript', 'storybook'],
    },
  },
};

export const ObjectInput: Story = {
  args: {
    inputs: {
      config: { key: 'value', nested: { deep: true } },
    },
  },
};

export const AllTypes: Story = {
  args: {
    inputs: {
      name: 'Test User',
      age: 25,
      active: true,
      tags: ['admin', 'developer'],
      preferences: { theme: 'dark', language: 'en' },
      status: 'pending',
    },
  },
};

export const LongValues: Story = {
  args: {
    inputs: {
      description: 'This is a very long string value that should be truncated when displayed to prevent overflow issues in the UI',
      data: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    },
  },
};

export const Empty: Story = {
  args: {
    inputs: {},
  },
};

export const NullValues: Story = {
  args: {
    inputs: {
      optional: null,
      missing: undefined,
      present: 'value',
    },
  },
};

export const CalculatorInputs: Story = {
  args: {
    inputs: {
      numbers: [10, 20, 30, 40],
      operation: 'sum',
    },
  },
};

export const ShowcaseInputs: Story = {
  args: {
    inputs: {
      user_name: 'John Doe',
      repeat_count: 3,
      formal: true,
      topics: ['AI', 'Machine Learning'],
      preferences: { color: 'blue' },
      language: 'english',
    },
  },
};
