import type { Meta, StoryObj } from '@storybook/react';
import { ValidationEventComponent } from './ValidationEventComponent';
import { ValidationEvent } from '@/types/events';

const meta = {
  title: 'Events/ValidationEventComponent',
  component: ValidationEventComponent,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof ValidationEventComponent>;

export default meta;
type Story = StoryObj<typeof meta>;

const baseTimestamp = new Date().toISOString();

export const ValidationPassed: Story = {
  args: {
    event: {
      event_type: 'validation',
      timestamp: baseTimestamp,
      valid: true,
      errors: [],
    } as ValidationEvent,
  },
};

export const SingleError: Story = {
  args: {
    event: {
      event_type: 'validation',
      timestamp: baseTimestamp,
      valid: false,
      errors: [
        {
          message: 'Undefined variable "foo"',
          line: 10,
          column: 5,
          severity: 'error',
        },
      ],
    } as ValidationEvent,
  },
};

export const MultipleErrors: Story = {
  args: {
    event: {
      event_type: 'validation',
      timestamp: baseTimestamp,
      valid: false,
      errors: [
        {
          message: 'Missing required field "model"',
          line: 5,
          severity: 'error',
        },
        {
          message: 'Invalid provider "unknown"',
          line: 8,
          column: 15,
          severity: 'error',
        },
        {
          message: 'Undefined variable "result"',
          line: 15,
          column: 10,
          severity: 'error',
        },
      ],
    } as ValidationEvent,
  },
};

export const SyntaxErrors: Story = {
  args: {
    event: {
      event_type: 'validation',
      timestamp: baseTimestamp,
      valid: false,
      errors: [
        {
          message: 'Unexpected token "end"',
          line: 20,
          column: 1,
          severity: 'error',
        },
        {
          message: 'Expected "then" but got "else"',
          line: 12,
          column: 5,
          severity: 'error',
        },
      ],
    } as ValidationEvent,
  },
};
