const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const log = require('electron-log');
const { BackendManager } = require('./backend-manager');
const { setupMenu } = require('./menu');

let mainWindow: any = null;
const backendManager = new BackendManager();

async function createWindow(frontendUrl: string, backendUrl: string) {
  const preloadPath = app.isPackaged
    ? path.join(process.resourcesPath, 'app.asar', 'dist', 'preload', 'preload.js')
    : path.join(__dirname, '../../dist/preload/preload.js');

  const window = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
    },
    title: 'Tactus IDE',
    show: false,
  });

  mainWindow = window;
  await window.loadURL(frontendUrl);
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
