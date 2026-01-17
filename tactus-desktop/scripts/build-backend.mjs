import { exec } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BACKEND_DIR = path.join(__dirname, '../backend');
const PROJECT_ROOT = path.join(__dirname, '../..');

function execPromise(command, options = {}) {
  return new Promise((resolve, reject) => {
    console.log(`Running: ${command}`);
    const child = exec(command, options, (error, stdout, stderr) => {
      if (error) {
        console.error(`Error: ${stderr}`);
        reject(error);
      } else {
        resolve(stdout);
      }
    });

    child.stdout?.on('data', (data) => process.stdout.write(data));
    child.stderr?.on('data', (data) => process.stderr.write(data));
  });
}

async function buildBackend() {
  console.log('========================================');
  console.log('Building Python backend with PyInstaller');
  console.log('========================================\n');

  // Detect Python command (prefer environment variable, then python for conda environments)
  let pythonCmd = process.env.PYTHON_CMD || 'python';
  if (!process.env.PYTHON_CMD) {
    try {
      await execPromise('python --version');
    } catch {
      pythonCmd = 'python3';
    }
  }

  // Check Python version
  console.log('Checking Python version...');
  const versionOutput = await execPromise(`${pythonCmd} --version`);
  console.log(`Using: ${versionOutput.trim()}`);

  // Ensure PyInstaller is installed
  console.log('Checking for PyInstaller...');
  try {
    const pyiVersion = await execPromise(`${pythonCmd} -m pip show pyinstaller`);
    console.log('PyInstaller is already installed');
  } catch (error) {
    console.log('PyInstaller not found, installing...');
    try {
      await execPromise(`${pythonCmd} -m pip install pyinstaller`);
    } catch (installError) {
      // Try with --break-system-packages for externally-managed environments
      console.log('Retrying with --break-system-packages flag...');
      await execPromise(`${pythonCmd} -m pip install --break-system-packages pyinstaller`);
    }
    console.log('PyInstaller installed successfully');
  }

  // Install Tactus package in development mode
  console.log('\nInstalling Tactus package...');
  try {
    await execPromise(`${pythonCmd} -m pip install -e .`, { cwd: PROJECT_ROOT });
  } catch (error) {
    // Try with --break-system-packages for externally-managed environments
    console.log('Retrying with --break-system-packages flag...');
    await execPromise(`${pythonCmd} -m pip install --break-system-packages -e .`, { cwd: PROJECT_ROOT });
  }

  // Build frontend first (needed for PyInstaller bundle)
  console.log('\nBuilding frontend for bundling...');
  const frontendDir = path.join(PROJECT_ROOT, 'tactus-ide', 'frontend');
  if (fs.existsSync(frontendDir)) {
    try {
      await execPromise('npm install', { cwd: frontendDir });
      await execPromise('npm run build', { cwd: frontendDir });
      console.log('Frontend built successfully');
    } catch (error) {
      console.warn('Warning: Frontend build failed, continuing anyway');
    }
  }

  // Run PyInstaller
  console.log('\nRunning PyInstaller...');
  await execPromise(`pyinstaller tactus_backend.spec --clean -y`, { cwd: BACKEND_DIR });

  console.log('\n========================================');
  console.log('Backend built successfully!');
  console.log(`Output: ${path.join(BACKEND_DIR, 'dist')}`);
  console.log('========================================');
}

buildBackend().catch((error) => {
  console.error('Build failed:', error);
  process.exit(1);
});
