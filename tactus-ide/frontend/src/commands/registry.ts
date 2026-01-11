/**
 * Command Registry
 * 
 * Single source of truth for all IDE commands.
 * Used by both in-app menubar and Electron OS menu.
 */

export interface Command {
  id: string;
  label: string;
  shortcut?: string;
  handler?: () => void | Promise<void>;
}

export interface CommandGroup {
  label: string;
  commands: Command[];
}

// Command handlers will be set by the App component
const commandHandlers = new Map<string, () => void | Promise<void>>();

export function registerCommandHandler(id: string, handler: () => void | Promise<void>) {
  commandHandlers.set(id, handler);
}

export function executeCommand(id: string) {
  const handler = commandHandlers.get(id);
  if (handler) {
    handler();
  } else {
    console.warn(`No handler registered for command: ${id}`);
  }
}

// Command definitions
export const FILE_COMMANDS: CommandGroup = {
  label: 'File',
  commands: [
    {
      id: 'file.openFolder',
      label: 'Open Folder...',
      shortcut: 'Cmd+O',
    },
    {
      id: 'file.save',
      label: 'Save',
      shortcut: 'Cmd+S',
    },
    {
      id: 'file.saveAs',
      label: 'Save As...',
      shortcut: 'Cmd+Shift+S',
    },
  ],
};

export const EDIT_COMMANDS: CommandGroup = {
  label: 'Edit',
  commands: [
    {
      id: 'edit.undo',
      label: 'Undo',
      shortcut: 'Cmd+Z',
    },
    {
      id: 'edit.redo',
      label: 'Redo',
      shortcut: 'Cmd+Shift+Z',
    },
    {
      id: 'edit.cut',
      label: 'Cut',
      shortcut: 'Cmd+X',
    },
    {
      id: 'edit.copy',
      label: 'Copy',
      shortcut: 'Cmd+C',
    },
    {
      id: 'edit.paste',
      label: 'Paste',
      shortcut: 'Cmd+V',
    },
  ],
};

export const VIEW_COMMANDS: CommandGroup = {
  label: 'View',
  commands: [
    {
      id: 'view.toggleLeftSidebar',
      label: 'Toggle Sidebar',
      shortcut: 'Ctrl+B / Cmd+B',
    },
    {
      id: 'view.toggleRightSidebar',
      label: 'Toggle Panel',
      shortcut: 'Cmd+Shift+B',
    },
  ],
};

export const RUN_COMMANDS: CommandGroup = {
  label: 'Procedure',
  commands: [
    {
      id: 'run.validate',
      label: 'Validate',
      shortcut: 'Cmd+Shift+V',
    },
    {
      id: 'run.run',
      label: 'Run',
      shortcut: 'Cmd+R',
    },
    {
      id: 'run.test',
      label: 'Test',
      shortcut: 'Cmd+Shift+T',
    },
    {
      id: 'run.evaluate',
      label: 'Evaluate',
      shortcut: 'Cmd+Shift+E',
    },
  ],
};

export const TACTUS_COMMANDS: CommandGroup = {
  label: 'Tactus',
  commands: [
    {
      id: 'tactus.preferences',
      label: 'Preferences...',
      shortcut: 'Cmd+,',
    },
    {
      id: 'tactus.about',
      label: 'About Tactus',
    },
  ],
};

// Tactus commands are shown in the logo dropdown, not in the menubar
export const ALL_COMMAND_GROUPS = [
  FILE_COMMANDS,
  EDIT_COMMANDS,
  VIEW_COMMANDS,
  RUN_COMMANDS,
];









