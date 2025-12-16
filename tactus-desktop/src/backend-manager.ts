import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import log from 'electron-log';

export class BackendManager {
  private process: ChildProcess | null = null;
  private serverPort: number = 0;

  async start(): Promise<{ backendPort: number; frontendPort: number }> {
    log.info('Starting Tactus IDE backend...');

    const tactusCommand = this.getTactusCommand();
    log.info(`Using tactus command: ${tactusCommand}`);

    // Get the examples folder path
    const examplesFolder = this.getExamplesFolder();
    log.info(`Setting working directory to: ${examplesFolder}`);

    // Spawn tactus ide with --no-browser
    this.process = spawn(tactusCommand, ['ide', '--no-browser'], {
      cwd: examplesFolder,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
      },
    });

    // Capture stdout to detect ports
    return new Promise((resolve, reject) => {
      let resolved = false;

      const timeout = setTimeout(() => {
        if (!resolved) {
          reject(new Error('Backend failed to start within 30 seconds'));
        }
      }, 30000);

      this.process!.stdout?.on('data', (data: Buffer) => {
        const output = data.toString();
        log.info(`[Backend] ${output}`);

        // Parse server port from "Server port: 5001"
        const serverMatch = output.match(/Server port: (\d+)/);
        if (serverMatch) {
          this.serverPort = parseInt(serverMatch[1], 10);
          log.info(`Detected server port: ${this.serverPort}`);
        }

        // Once server is confirmed started, resolve
        if (output.includes('Server started') && this.serverPort) {
          if (!resolved) {
            resolved = true;
            clearTimeout(timeout);
            // Return the same port for both backend and frontend since they're unified
            resolve({ backendPort: this.serverPort, frontendPort: this.serverPort });
          }
        }
      });

      this.process!.stderr?.on('data', (data: Buffer) => {
        log.error(`[Backend Error] ${data.toString()}`);
      });

      this.process!.on('exit', (code) => {
        log.warn(`Backend process exited with code ${code}`);
        if (!resolved) {
          resolved = true;
          clearTimeout(timeout);
          reject(new Error(`Backend process exited with code ${code}`));
        }
      });

      this.process!.on('error', (error) => {
        log.error(`Backend process error: ${error}`);
        if (!resolved) {
          resolved = true;
          clearTimeout(timeout);
          reject(error);
        }
      });
    });
  }

  private getExamplesFolder(): string {
    const { app } = require('electron');
    const isDev = !app.isPackaged;

    if (isDev) {
      // Development: use examples folder from project root
      // Navigate from tactus-desktop to project root
      return path.join(__dirname, '..', '..', '..', 'examples');
    }

    // Production: use bundled examples folder
    const examplesPath = path.join(process.resourcesPath, 'examples');

    if (fs.existsSync(examplesPath)) {
      return examplesPath;
    }

    // Fallback to user's home directory
    log.warn('Examples folder not found, using home directory');
    return app.getPath('home');
  }

  private getTactusCommand(): string {
    const { app } = require('electron');
    const isDev = !app.isPackaged;

    if (isDev) {
      // Development: use tactus from system PATH
      return 'tactus';
    }

    // Production: use bundled executable
    // PyInstaller creates a directory structure: backend/tactus/tactus (executable)
    const platform = process.platform;
    const ext = platform === 'win32' ? '.exe' : '';
    const tactusPath = path.join(
      process.resourcesPath,
      'backend',
      'tactus',
      `tactus${ext}`
    );

    if (fs.existsSync(tactusPath)) {
      return tactusPath;
    }

    // Fallback to system tactus
    log.warn('Bundled tactus not found, falling back to system tactus');
    return 'tactus';
  }

  stop(): void {
    if (this.process) {
      log.info('Stopping backend process...');
      this.process.kill();
      this.process = null;
    }
  }

  getBackendUrl(): string {
    return `http://127.0.0.1:${this.serverPort}`;
  }

  getFrontendUrl(): string {
    return `http://127.0.0.1:${this.serverPort}`;
  }
}
