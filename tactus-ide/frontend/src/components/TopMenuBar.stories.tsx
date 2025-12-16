import type { Meta, StoryObj } from '@storybook/react';
import { Menubar, MenubarContent, MenubarItem, MenubarMenu, MenubarShortcut, MenubarTrigger } from './ui/menubar';
import { Separator } from './ui/separator';
import { Button } from './ui/button';
import { Logo } from './ui/logo';
import { Mail, Bell } from 'lucide-react';
import { ALL_COMMAND_GROUPS } from '@/commands/registry';

// Create a wrapper component for the top menu bar
const TopMenuBar = ({ 
  workspaceName, 
  currentFile, 
  hasUnsavedChanges 
}: { 
  workspaceName?: string | null; 
  currentFile?: string | null; 
  hasUnsavedChanges?: boolean;
}) => {
  return (
    <div className="flex items-center justify-between h-12 px-4 border-b bg-card">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Logo className="h-6 w-auto" />
          <span className="font-semibold">Tactus</span>
        </div>
        <Separator orientation="vertical" className="h-6" />
        <Menubar className="border-0 bg-transparent shadow-none">
          {ALL_COMMAND_GROUPS.map((group) => (
            <MenubarMenu key={group.label}>
              <MenubarTrigger>{group.label}</MenubarTrigger>
              <MenubarContent>
                {group.commands.map((cmd) => (
                  <MenubarItem key={cmd.id} onClick={() => console.log('Command:', cmd.id)}>
                    {cmd.label}
                    {cmd.shortcut && <MenubarShortcut>{cmd.shortcut}</MenubarShortcut>}
                  </MenubarItem>
                ))}
              </MenubarContent>
            </MenubarMenu>
          ))}
        </Menubar>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">
          {workspaceName || 'No folder open'}
          {currentFile && ` • ${currentFile}`}
          {hasUnsavedChanges && ' •'}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon">
          <Mail className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon">
          <Bell className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
};

const meta = {
  title: 'Layout/TopMenuBar',
  component: TopMenuBar,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof TopMenuBar>;

export default meta;
type Story = StoryObj<typeof meta>;

export const NoWorkspace: Story = {
  args: {
    workspaceName: null,
    currentFile: null,
    hasUnsavedChanges: false,
  },
};

export const WithWorkspace: Story = {
  args: {
    workspaceName: 'tactus-examples',
    currentFile: null,
    hasUnsavedChanges: false,
  },
};

export const WithOpenFile: Story = {
  args: {
    workspaceName: 'tactus-examples',
    currentFile: 'simple-agent.tac',
    hasUnsavedChanges: false,
  },
};

export const WithUnsavedChanges: Story = {
  args: {
    workspaceName: 'tactus-examples',
    currentFile: 'simple-agent.tac',
    hasUnsavedChanges: true,
  },
};

export const LongFilePath: Story = {
  args: {
    workspaceName: 'my-project',
    currentFile: 'src/procedures/complex/deeply/nested/path/to/my-agent.tac',
    hasUnsavedChanges: true,
  },
};
