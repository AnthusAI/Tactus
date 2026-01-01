/**
 * LSP client for Tactus IDE using HTTP polling instead of WebSocket.
 * 
 * This avoids WebSocket compatibility issues with Flask.
 */

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

export class LSPClientHTTP {
  private baseUrl: string;
  private messageId = 0;
  private diagnosticsHandler?: (diagnostics: LSPDiagnostic[]) => void;
  private currentUri = 'file:///untitled.tac';
  private version = 0;
  private isConnected = false;
  
  constructor(url?: string) {
    // Use environment variable if available, otherwise use provided URL or default
    this.baseUrl = url || import.meta.env.VITE_BACKEND_URL || 'http://localhost:5001';
    this.checkConnection();
  }
  
  private async checkConnection() {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      if (response.ok) {
        this.isConnected = true;
        console.log('LSP client connected (HTTP)');
        await this.initialize();
      }
    } catch (error) {
      console.warn('LSP connection failed:', error);
      this.isConnected = false;
    }
  }
  
  async initialize(): Promise<any> {
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
    this.isConnected = false;
  }
  
  private async send(method: string, params: any): Promise<any> {
    if (!this.isConnected) {
      return Promise.resolve(null);
    }
    
    const id = this.messageId++;
    
    try {
      const response = await fetch(`${this.baseUrl}/api/lsp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0',
          id,
          method,
          params
        })
      });
      
      if (!response.ok) {
        return null;
      }
      
      const data = await response.json();
      
      // Handle diagnostics if present
      if (data.method === 'textDocument/publishDiagnostics' && this.diagnosticsHandler) {
        this.diagnosticsHandler(data.params.diagnostics);
      }
      
      return data.result;
    } catch (error) {
      console.warn('LSP request failed:', error);
      return null;
    }
  }
  
  private async sendNotification(method: string, params: any) {
    if (!this.isConnected) return;
    
    try {
      const response = await fetch(`${this.baseUrl}/api/lsp/notification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0',
          method,
          params
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        // Handle diagnostics if present
        if (data.diagnostics && this.diagnosticsHandler) {
          this.diagnosticsHandler(data.diagnostics);
        }
      }
    } catch (error) {
      console.warn('LSP notification failed:', error);
    }
  }
}












