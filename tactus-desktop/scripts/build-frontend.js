import { exec } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const FRONTEND_SRC = path.join(__dirname, '../../tactus-ide/frontend/dist');
const FRONTEND_DEST = path.join(__dirname, '../frontend/dist');

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

function copyRecursiveSync(src, dest) {
  const exists = fs.existsSync(src);
  const stats = exists && fs.statSync(src);
  const isDirectory = exists && stats.isDirectory();

  if (isDirectory) {
    if (!fs.existsSync(dest)) {
      fs.mkdirSync(dest, { recursive: true });
    }
    fs.readdirSync(src).forEach((childItemName) => {
      copyRecursiveSync(
        path.join(src, childItemName),
        path.join(dest, childItemName)
      );
    });
  } else {
    fs.copyFileSync(src, dest);
  }
}

async function buildFrontend() {
  console.log('========================================');
  console.log('Building React frontend');
  console.log('========================================\n');

  const frontendDir = path.join(__dirname, '../../tactus-ide/frontend');

  if (!fs.existsSync(frontendDir)) {
    console.error(`Frontend directory not found: ${frontendDir}`);
    process.exit(1);
  }

  // Install dependencies
  console.log('Installing dependencies...');
  await execPromise('npm install', { cwd: frontendDir });

  // Build with Vite
  console.log('\nBuilding with Vite...');
  await execPromise('npm run build', {
    cwd: frontendDir,
    env: {
      ...process.env,
      VITE_BACKEND_URL: 'http://127.0.0.1:{{PORT}}' // Placeholder, replaced at runtime
    }
  });

  // Copy dist to Electron app
  console.log('\nCopying build to Electron app...');
  if (fs.existsSync(FRONTEND_DEST)) {
    fs.rmSync(FRONTEND_DEST, { recursive: true });
  }
  copyRecursiveSync(FRONTEND_SRC, FRONTEND_DEST);

  console.log('\n========================================');
  console.log('Frontend built successfully!');
  console.log(`Output: ${FRONTEND_DEST}`);
  console.log('========================================');
}

buildFrontend().catch((error) => {
  console.error('Build failed:', error);
  process.exit(1);
});
