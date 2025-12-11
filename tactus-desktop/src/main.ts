import { app, BrowserWindow } from 'electron';
import * as path from 'path';
import log from 'electron-log';
import { BackendManager } from './backend-manager';
import { setupMenu } from './menu';

let mainWindow: BrowserWindow | null = null;
const backendManager = new BackendManager();

async function createWindow(frontendUrl: string, backendUrl: string) {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      preload: path.join(__dirname, '../../dist/preload/preload.js'),
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

  // Setup menu
  setupMenu();
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
