/**
 * LSP client for Tactus IDE.
 * 
 * Communicates with the Python LSP backend via WebSocket (Socket.IO).
 * Provides semantic validation and intelligence features.
 */
import { io, Socket } from 'socket.io-client';

export interface LSPDiagnostic {
  range: {
    start: { line: number; character: number };
    end: { line: number; character: number };
  };
  severity: number;
  source: string;
  message: string;
}

export interface LSPCompletionItem {
  label: string;
  kind: number;
  insertText?: string;
  insertTextFormat?: number;
  documentation?: string;
  detail?: string;
}

export class LSPClient {
  private socket: Socket;
  private messageId = 0;
  private callbacks = new Map<number, (result: any) => void>();
  private diagnosticsHandler?: (diagnostics: LSPDiagnostic[]) => void;
  private currentUri = 'file:///untitled.tac';
  private version = 0;
  private isConnected = false;
  
  constructor(url: string = 'http://localhost:5001') {
    this.socket = io(url, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5,
      timeout: 5000
    });
    
    this.socket.on('connect', () => {
      console.log('LSP client connected');
      this.isConnected = true;
      this.initialize();
    });
    
    this.socket.on('disconnect', () => {
      console.log('LSP client disconnected');
      this.isConnected = false;
    });
    
    this.socket.on('connect_error', (error) => {
      console.warn('LSP connection error:', error.message);
      this.isConnected = false;
    });
    
    this.socket.on('lsp', (message: any) => {
      this.handleMessage(message);
    });
  }
  
  initialize(): Promise<any> {
    return this.send('initialize', {
      capabilities: {
        textDocument: {
          synchronization: { dynamicRegistration: true },
          completion: { dynamicRegistration: true },
          hover: { dynamicRegistration: true },
          signatureHelp: { dynamicRegistration: true }
        }
      }
    });
  }
  
  didOpen(uri: string, text: string) {
    if (!this.isConnected) return;
    
    this.currentUri = uri;
    this.version = 0;
    this.sendNotification('textDocument/didOpen', {
      textDocument: {
        uri,
        languageId: 'tactus-lua',
        version: this.version,
        text
      }
    });
  }
  
  didChange(text: string) {
    if (!this.isConnected) return;
    
    this.version++;
    this.sendNotification('textDocument/didChange', {
      textDocument: { uri: this.currentUri, version: this.version },
      contentChanges: [{ text }]
    });
  }
  
  didClose() {
    if (!this.isConnected) return;
    
    this.sendNotification('textDocument/didClose', {
      textDocument: { uri: this.currentUri }
    });
  }
  
  async requestCompletions(position: { line: number; character: number }): Promise<LSPCompletionItem[]> {
    const result = await this.send('textDocument/completion', {
      textDocument: { uri: this.currentUri },
      position
    });
    return result?.items || [];
  }
  
  async requestHover(position: { line: number; character: number }): Promise<any> {
    return this.send('textDocument/hover', {
      textDocument: { uri: this.currentUri },
      position
    });
  }
  
  async requestSignatureHelp(position: { line: number; character: number }): Promise<any> {
    return this.send('textDocument/signatureHelp', {
      textDocument: { uri: this.currentUri },
      position
    });
  }
  
  onDiagnostics(handler: (diagnostics: LSPDiagnostic[]) => void) {
    this.diagnosticsHandler = handler;
  }
  
  disconnect() {
    this.socket.disconnect();
  }
  
  private handleMessage(message: any) {
    if (message.method === 'textDocument/publishDiagnostics') {
      // Semantic errors from LSP
      if (this.diagnosticsHandler) {
        this.diagnosticsHandler(message.params.diagnostics);
      }
    } else if (message.id !== undefined) {
      // Response to request
      const callback = this.callbacks.get(message.id);
      if (callback) {
        callback(message.result);
        this.callbacks.delete(message.id);
      }
    }
  }
  
  private send(method: string, params: any): Promise<any> {
    if (!this.isConnected) {
      return Promise.resolve(null);
    }
    
    const id = this.messageId++;
    
    return new Promise((resolve) => {
      this.callbacks.set(id, resolve);
      this.socket.emit('lsp', {
        jsonrpc: '2.0',
        id,
        method,
        params
      });
      
      // Timeout after 5 seconds
      setTimeout(() => {
        if (this.callbacks.has(id)) {
          this.callbacks.delete(id);
          resolve(null);
        }
      }, 5000);
    });
  }
  
  private sendNotification(method: string, params: any) {
    if (!this.isConnected) return;
    
    this.socket.emit('lsp_notification', {
      jsonrpc: '2.0',
      method,
      params
    });
  }
}












