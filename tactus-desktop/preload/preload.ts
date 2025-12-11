import { contextBridge, ipcRenderer } from 'electron';

// Expose protected methods that allow the renderer process to use
// ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Add IPC methods here if needed in the future
  // For now, the IDE uses the backend's /api/file endpoints
});
