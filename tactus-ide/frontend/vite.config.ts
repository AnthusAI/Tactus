/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';
import path from 'path';

const hitlComponentsRoot = path.resolve(
  __dirname,
  '../../../Tactus-HITL-components/src'
);
const hitlComponentsFallback = path.resolve(
  __dirname,
  './vendor/tactus-hitl-components/src'
);
const hitlComponentsPath = fs.existsSync(hitlComponentsRoot)
  ? hitlComponentsRoot
  : hitlComponentsFallback;

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@anthus/tactus-hitl-components': hitlComponentsPath,
    }
  },
  server: {
    port: process.env.PORT ? parseInt(process.env.PORT) : 3000,
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://localhost:5001',
        changeOrigin: true
      }
    }
  }
});
