import type { BrowserWindow } from 'electron';

let preferencesWindow: BrowserWindow | null = null;

export function createPreferencesWindow(frontendUrl: string, preloadPath: string): void {
  const { BrowserWindow } = require('electron');

  // If preferences window already exists, focus it
  if (preferencesWindow && !preferencesWindow.isDestroyed()) {
    preferencesWindow.focus();
    return;
  }

  const newWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
    },
    title: 'Preferences',
    show: false,
    minimizable: false,
    maximizable: false,
  });

  preferencesWindow = newWindow;

  // Load the frontend URL with a preferences-only parameter
  // This tells the frontend to show ONLY the preferences UI
  newWindow.loadURL(`${frontendUrl}?preferencesOnly=true`);

  newWindow.once('ready-to-show', () => {
    if (preferencesWindow && !preferencesWindow.isDestroyed()) {
      preferencesWindow.show();
    }
  });

  newWindow.on('closed', () => {
    preferencesWindow = null;
  });
}

export function getPreferencesWindow(): BrowserWindow | null {
  return preferencesWindow;
}
