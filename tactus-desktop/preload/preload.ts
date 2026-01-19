const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Command dispatch from menu
  onCommand: (callback: (cmdId: string) => void) => {
    ipcRenderer.on('tactus:command', (_event: any, data: any) => {
      callback(data.id);
    });
  },

  // Native folder selection dialog
  selectWorkspaceFolder: async (): Promise<string | null> => {
    return await ipcRenderer.invoke('select-workspace-folder');
  },

  // Open preferences window
  openPreferences: async (): Promise<void> => {
    return await ipcRenderer.invoke('open-preferences');
  },
});

console.log('Preload script loaded successfully - electronAPI exposed');
