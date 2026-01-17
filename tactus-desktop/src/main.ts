const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const log = require('electron-log');
const { BackendManager } = require('./backend-manager');
const { setupMenu } = require('./menu');
const { createPreferencesWindow } = require('./preferences-window');

let mainWindow: any = null;
let frontendUrl: string = '';
let preloadPath: string = '';
const backendManager = new BackendManager();

async function createWindow(url: string, backendUrl: string) {
  const localPreloadPath = app.isPackaged
    ? path.join(process.resourcesPath, 'app.asar', 'dist', 'preload', 'preload.js')
    : path.join(__dirname, '../../dist/preload/preload.js');

  // Store globally for preferences window
  frontendUrl = url;
  preloadPath = localPreloadPath;

  const window = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      preload: localPreloadPath,
      contextIsolation: true,
      nodeIntegration: false,
    },
    title: 'Tactus IDE',
    show: false,
  });

  mainWindow = window;
  await window.loadURL(url);
  window.once('ready-to-show', () => { window.show(); });
  window.on('closed', () => { mainWindow = null; });
  setupMenu(window);
}

app.on('ready', async () => {
  try {
    app.name = 'Tactus IDE';

    ipcMain.handle('select-workspace-folder', async () => {
      if (!mainWindow) return null;
      const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory'],
        title: 'Select Workspace Folder',
      });
      if (result.canceled || result.filePaths.length === 0) return null;
      return result.filePaths[0];
    });

    ipcMain.handle('open-preferences', async () => {
      if (frontendUrl && preloadPath) {
        createPreferencesWindow(frontendUrl, preloadPath);
      }
    });

    log.info('Starting Tactus IDE Desktop App');
    const { backendPort, frontendPort } = await backendManager.start();
    const frontendUrl = `http://127.0.0.1:${frontendPort}`;
    const backendUrl = `http://127.0.0.1:${backendPort}`;
    await createWindow(frontendUrl, backendUrl);
  } catch (error) {
    log.error('Failed to start application:', error);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  backendManager.stop();
});

app.on('activate', async () => {
  if (mainWindow === null) {
    try {
      const { backendPort, frontendPort } = await backendManager.start();
      await createWindow(`http://127.0.0.1:${frontendPort}`, `http://127.0.0.1:${backendPort}`);
    } catch (error) {
      log.error('Failed to reactivate application:', error);
    }
  }
});

// Export function to open preferences window
export function openPreferencesWindow(): void {
  if (frontendUrl && preloadPath) {
    createPreferencesWindow(frontendUrl, preloadPath);
  }
}

export function getMainWindow(): any {
  return mainWindow;
}
