import type { Meta, StoryObj } from '@storybook/react';
import { Duration } from './Duration';
import React, { useState, useEffect } from 'react';

const meta = {
  title: 'Components/Duration',
  component: Duration,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof Duration>;

export default meta;
type Story = StoryObj<typeof meta>;

// Wrapper component that creates timestamp on mount
const DurationWrapper: React.FC<{ secondsOffset: number }> = ({ secondsOffset }) => {
  const [startTime] = useState(() => new Date(Date.now() - secondsOffset * 1000).toISOString());
  return <Duration startTime={startTime} />;
};

export const JustStarted: Story = {
  render: () => <DurationWrapper secondsOffset={0} />,
};

export const FiveSeconds: Story = {
  render: () => <DurationWrapper secondsOffset={5} />,
};

export const ThirtySeconds: Story = {
  render: () => <DurationWrapper secondsOffset={30} />,
};

export const OneMinute: Story = {
  render: () => <DurationWrapper secondsOffset={65} />,
};

export const FiveMinutes: Story = {
  render: () => <DurationWrapper secondsOffset={305} />,
};

export const OneHour: Story = {
  render: () => <DurationWrapper secondsOffset={3665} />,
};

export const TwoHours: Story = {
  render: () => <DurationWrapper secondsOffset={7325} />,
};
