import type { Meta, StoryObj } from '@storybook/react';
import { Logo } from './logo';

const meta = {
  title: 'UI/Logo',
  component: Logo,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof Logo>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {},
  render: (args) => (
    <div className="p-8 bg-background text-foreground">
      <Logo {...args} />
    </div>
  ),
};

export const SmallContainer: Story = {
  render: (args) => (
    <div className="p-8 bg-background text-foreground">
      <div style={{ width: '100px', height: '33px' }}>
        <Logo {...args} />
      </div>
    </div>
  ),
};

export const LargeContainer: Story = {
  render: (args) => (
    <div className="p-8 bg-background text-foreground">
      <div style={{ width: '500px', height: '166px' }}>
        <Logo {...args} />
      </div>
    </div>
  ),
};

export const WithCustomColor: Story = {
  render: (args) => (
    <div className="p-8 bg-background">
      <div className="space-y-4">
        <div className="text-primary">
          <Logo {...args} />
        </div>
        <div className="text-destructive">
          <Logo {...args} />
        </div>
        <div className="text-muted-foreground">
          <Logo {...args} />
        </div>
      </div>
    </div>
  ),
};

export const WithoutText: Story = {
  args: {
    showText: false,
  },
  render: (args) => (
    <div className="p-8 bg-background text-foreground">
      <Logo {...args} />
    </div>
  ),
};

export const IconOnly: Story = {
  args: {
    showText: false,
  },
  render: (args) => (
    <div className="p-8 bg-background text-foreground">
      <div style={{ width: '50px', height: '50px' }}>
        <Logo {...args} />
      </div>
    </div>
  ),
};

export const LargeDesignView: Story = {
  args: {},
  render: (args) => (
    <div className="min-h-screen flex items-center justify-center bg-background text-foreground p-8">
      <div style={{ fontSize: '8rem' }}>
        <Logo {...args} />
      </div>
    </div>
  ),
  parameters: {
    layout: 'fullscreen',
  },
};
