import { spawn, ChildProcess } from 'child_process';
import { app } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import log from 'electron-log';

export class BackendManager {
  private process: ChildProcess | null = null;
  private backendPort: number = 0;
  private frontendPort: number = 0;

  async start(): Promise<{ backendPort: number; frontendPort: number }> {
    log.info('Starting Tactus IDE backend...');

    const tactusCommand = this.getTactusCommand();
    log.info(`Using tactus command: ${tactusCommand}`);

    // Spawn tactus ide with --no-browser
    this.process = spawn(tactusCommand, ['ide', '--no-browser'], {
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

        // Parse backend port
        const backendMatch = output.match(/Backend port: (\d+)/);
        if (backendMatch) {
          this.backendPort = parseInt(backendMatch[1], 10);
          log.info(`Detected backend port: ${this.backendPort}`);
        }

        // Parse frontend port
        const frontendMatch = output.match(/Frontend port: (\d+)/);
        if (frontendMatch) {
          this.frontendPort = parseInt(frontendMatch[1], 10);
          log.info(`Detected frontend port: ${this.frontendPort}`);
        }

        // Check if both servers are ready
        if (output.includes('Frontend server started') && this.backendPort && this.frontendPort) {
          if (!resolved) {
            resolved = true;
            clearTimeout(timeout);
            resolve({ backendPort: this.backendPort, frontendPort: this.frontendPort });
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

  private getTactusCommand(): string {
    const isDev = !app.isPackaged;

    if (isDev) {
      // Development: use tactus from system PATH
      return 'tactus';
    }

    // Production: use bundled executable
    const platform = process.platform;
    const ext = platform === 'win32' ? '.exe' : '';
    const tactusPath = path.join(
      process.resourcesPath,
      'backend',
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
    return `http://127.0.0.1:${this.backendPort}`;
  }

  getFrontendUrl(): string {
    return `http://127.0.0.1:${this.frontendPort}`;
  }
}
