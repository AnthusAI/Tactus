import type { Meta, StoryObj } from '@storybook/react';
import { LoadingEventComponent } from './LoadingEventComponent';
import { LoadingEvent } from '@/types/events';
import React, { useState } from 'react';

const meta = {
  title: 'Events/LoadingEventComponent',
  component: LoadingEventComponent,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof LoadingEventComponent>;

export default meta;
type Story = StoryObj<typeof meta>;

// Wrapper component that creates timestamp on mount
const LoadingWrapper: React.FC<{ message: string }> = ({ message }) => {
  const [event] = useState<LoadingEvent>(() => ({
    event_type: 'loading',
    message,
    timestamp: new Date().toISOString(),
  }));
  return <LoadingEventComponent event={event} key={event.timestamp} />;
};

export const Default: Story = {
  render: () => <LoadingWrapper message="Processing..." />,
};

export const RunningAgent: Story = {
  render: () => <LoadingWrapper message="Running agent..." />,
};

export const ExecutingTest: Story = {
  render: () => <LoadingWrapper message="Executing test scenario..." />,
};

export const WaitingForResponse: Story = {
  render: () => <LoadingWrapper message="Waiting for LLM response..." />,
};

export const ProcessingData: Story = {
  render: () => <LoadingWrapper message="Processing data..." />,
};

export const InitializingAgent: Story = {
  render: () => <LoadingWrapper message="Initializing agent..." />,
};
