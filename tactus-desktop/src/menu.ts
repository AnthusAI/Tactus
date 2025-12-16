import type { BrowserWindow } from 'electron';

export function setupMenu(mainWindow: BrowserWindow): void {
  const { app, Menu } = require('electron');

  const sendCommand = (cmdId: string) => {
    mainWindow.webContents.send('tactus:command', { id: cmdId });
  };

  const template: Electron.MenuItemConstructorOptions[] = [
    {
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: 'File',
      submenu: [
        {
          label: 'Open Folder...',
          accelerator: 'CmdOrCtrl+O',
          click: () => sendCommand('file.openFolder'),
        },
        { type: 'separator' },
        {
          label: 'Save',
          accelerator: 'CmdOrCtrl+S',
          click: () => sendCommand('file.save'),
        },
        {
          label: 'Save As...',
          accelerator: 'CmdOrCtrl+Shift+S',
          click: () => sendCommand('file.saveAs'),
        },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
    {
      label: 'View',
      submenu: [
        {
          label: 'Toggle File Tree',
          accelerator: 'CmdOrCtrl+B',
          click: () => sendCommand('view.toggleLeftSidebar'),
        },
        {
          label: 'Toggle Chat',
          accelerator: 'CmdOrCtrl+Shift+B',
          click: () => sendCommand('view.toggleRightSidebar'),
        },
        {
          label: 'Toggle Metrics',
          accelerator: 'CmdOrCtrl+J',
          click: () => sendCommand('view.toggleBottomDrawer'),
        },
        { type: 'separator' },
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
      ],
    },
    {
      label: 'Procedure',
      submenu: [
        {
          label: 'Validate',
          accelerator: 'CmdOrCtrl+Shift+V',
          click: () => sendCommand('run.validate'),
        },
        {
          label: 'Run',
          accelerator: 'CmdOrCtrl+R',
          click: () => sendCommand('run.run'),
        },
        {
          label: 'Test',
          accelerator: 'CmdOrCtrl+Shift+T',
          click: () => sendCommand('run.test'),
        },
        {
          label: 'Evaluate',
          accelerator: 'CmdOrCtrl+Shift+E',
          click: () => sendCommand('run.evaluate'),
        },
      ],
    },
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'zoom' },
        { type: 'separator' },
        { role: 'close' },
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}
