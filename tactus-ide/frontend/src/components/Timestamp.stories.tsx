import type { Meta, StoryObj } from '@storybook/react';
import { Timestamp } from './Timestamp';

const meta = {
  title: 'Components/Timestamp',
  component: Timestamp,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof Timestamp>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    timestamp: new Date().toISOString(),
  },
};

export const Morning: Story = {
  args: {
    timestamp: new Date('2024-01-15T09:30:45').toISOString(),
  },
};

export const Afternoon: Story = {
  args: {
    timestamp: new Date('2024-01-15T14:22:10').toISOString(),
  },
};

export const Evening: Story = {
  args: {
    timestamp: new Date('2024-01-15T18:45:30').toISOString(),
  },
};

export const Night: Story = {
  args: {
    timestamp: new Date('2024-01-15T23:59:59').toISOString(),
  },
};
