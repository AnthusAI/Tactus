import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import * as path from 'path';
import { fileURLToPath } from 'url';
import log from 'electron-log';
import { BackendManager } from './backend-manager.js';
import { setupMenu } from './menu.js';

// ES module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Set the app name explicitly (fixes "Electron" showing on macOS in dev mode)
app.name = 'Tactus IDE';

let mainWindow: BrowserWindow | null = null;
const backendManager = new BackendManager();

// Get preload path - works in both dev and production
function getPreloadPath(): string {
  if (app.isPackaged) {
    // Production: preload is packaged in app.asar
    return path.join(process.resourcesPath, 'app.asar', 'dist', 'preload', 'preload.js');
  } else {
    // Development: preload is in dist directory
    return path.join(__dirname, '..', '..', 'dist', 'preload', 'preload.js');
  }
}

// IPC handler for workspace folder selection
ipcMain.handle('select-workspace-folder', async () => {
  if (!mainWindow) return null;
  
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: 'Select Workspace Folder',
  });
  
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  
  return result.filePaths[0];
});

async function createWindow(frontendUrl: string, backendUrl: string) {
  const preloadPath = getPreloadPath();
  log.info(`Preload path: ${preloadPath}`);

  mainWindow = new BrowserWindow({
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

  // Load the frontend URL
  log.info(`Loading frontend from: ${frontendUrl}`);
  await mainWindow.loadURL(frontendUrl);

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Setup menu with window reference
  setupMenu(mainWindow);
}

app.on('ready', async () => {
  try {
    log.info('Starting Tactus IDE Desktop App');

    // Start backend (which also starts frontend server)
    const { backendPort, frontendPort } = await backendManager.start();
    const frontendUrl = `http://127.0.0.1:${frontendPort}`;
    const backendUrl = `http://127.0.0.1:${backendPort}`;

    log.info(`Backend URL: ${backendUrl}`);
    log.info(`Frontend URL: ${frontendUrl}`);

    // Create window
    await createWindow(frontendUrl, backendUrl);

  } catch (error) {
    log.error('Failed to start application:', error);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  backendManager.stop();
});

app.on('activate', async () => {
  if (mainWindow === null) {
    try {
      const { backendPort, frontendPort } = await backendManager.start();
      const frontendUrl = `http://127.0.0.1:${frontendPort}`;
      const backendUrl = `http://127.0.0.1:${backendPort}`;
      await createWindow(frontendUrl, backendUrl);
    } catch (error) {
      log.error('Failed to reactivate application:', error);
    }
  }
});
