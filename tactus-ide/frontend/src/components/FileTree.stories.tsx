import type { Meta, StoryObj } from '@storybook/react';
import { FileTree } from './FileTree';

const meta = {
  title: 'Layout/FileTree',
  component: FileTree,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof FileTree>;

export default meta;
type Story = StoryObj<typeof meta>;

export const NoWorkspace: Story = {
  args: {
    workspaceRoot: null,
    workspaceName: null,
    onFileSelect: (path: string) => console.log('Selected:', path),
    selectedFile: null,
  },
};

export const WithWorkspace: Story = {
  args: {
    workspaceRoot: '/Users/example/projects/tactus',
    workspaceName: 'tactus',
    onFileSelect: (path: string) => console.log('Selected:', path),
    selectedFile: null,
  },
};

export const WithSelectedFile: Story = {
  args: {
    workspaceRoot: '/Users/example/projects/tactus/examples',
    workspaceName: 'examples',
    onFileSelect: (path: string) => console.log('Selected:', path),
    selectedFile: '/Users/example/projects/tactus/examples/simple-agent.tac',
  },
};
