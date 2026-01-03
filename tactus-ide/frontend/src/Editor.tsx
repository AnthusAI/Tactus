/**
 * Main editor component for Tactus IDE.
 *
 * Uses hybrid validation:
 * 1. TypeScript parser for instant syntax validation
 * 2. Python LSP for semantic intelligence
 */
import React, { useEffect, useRef, useState, useImperativeHandle, forwardRef } from 'react';
import * as monaco from 'monaco-editor';
import { LSPClientHTTP as LSPClient, LSPDiagnostic } from './LSPClientHTTP';
import { TactusValidator } from './validation/TactusValidator';
import { registerTactusLanguage } from './TactusLanguage';

interface EditorProps {
  initialValue?: string;
  onValueChange?: (value: string) => void;
  filePath?: string;
}

export interface EditorHandle {
  revealLine: (lineNumber: number) => void;
}

export const Editor = forwardRef<EditorHandle, EditorProps>(({ initialValue = '', onValueChange, filePath }, ref) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor>();
  const modelRef = useRef<monaco.editor.ITextModel>();
  const lspClient = useRef<LSPClient>();
  const tsValidator = useRef(new TactusValidator());
  const lspTimer = useRef<NodeJS.Timeout>();
  const [lspConnected, setLspConnected] = useState(false);
  const isDisposedRef = useRef(false);
  const onValueChangeRef = useRef(onValueChange);
  const currentFileUri = useRef<string>('file:///untitled.tac');
  const currentDecorationRef = useRef<monaco.editor.IEditorDecorationsCollection | null>(null);
  const [isDark, setIsDark] = useState(() =>
    window.matchMedia('(prefers-color-scheme: dark)').matches
  );
  
  // Update the callback ref when it changes
  useEffect(() => {
    onValueChangeRef.current = onValueChange;
  }, [onValueChange]);

  // Expose revealLine method to parent via ref
  useImperativeHandle(ref, () => ({
    revealLine: (lineNumber: number) => {
      if (!editorRef.current) return;

      console.log('Editor.revealLine called with lineNumber:', lineNumber);

      // Reveal the line in the center of the editor
      editorRef.current.revealLineInCenter(lineNumber);

      // Set cursor position to the line
      editorRef.current.setPosition({
        lineNumber: lineNumber,
        column: 1
      });

      // Clear previous decoration if it exists
      if (currentDecorationRef.current) {
        currentDecorationRef.current.clear();
        currentDecorationRef.current = null;
      }

      // Add a persistent highlight decoration to the line
      currentDecorationRef.current = editorRef.current.createDecorationsCollection([
        {
          range: new monaco.Range(lineNumber, 1, lineNumber, 1),
          options: {
            isWholeLine: true,
            className: 'highlighted-line-persistent',
            glyphMarginClassName: 'highlighted-line-glyph',
            overviewRuler: {
              color: '#fbbf24',
              position: monaco.editor.OverviewRulerLane.Full
            }
          }
        }
      ]);

      // Focus the editor
      editorRef.current.focus();
    }
  }), []);

  // Listen for system theme changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const handleChange = (e: MediaQueryListEvent) => {
      setIsDark(e.matches);
      if (editorRef.current) {
        monaco.editor.setTheme(e.matches ? 'tactus-dark' : 'tactus-light');
      }
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);
  
  // Handle file changes (initialValue and filePath)
  useEffect(() => {
    if (!editorRef.current || !lspClient.current) return;
    
    const currentValue = editorRef.current.getValue();
    const newUri = filePath ? `file:///${filePath}` : 'file:///untitled.tac';
    
    // If file changed, notify LSP
    if (newUri !== currentFileUri.current) {
      // Close old file
      if (lspConnected) {
        lspClient.current.didClose();
      }
      
      currentFileUri.current = newUri;
      
      // Open new file
      if (lspConnected) {
        lspClient.current.didOpen(newUri, initialValue || '');
      }
    }
    
    // Update content if changed
    if (currentValue !== initialValue) {
      editorRef.current.setValue(initialValue || '');
    }
  }, [initialValue, filePath, lspConnected]);
  
  useEffect(() => {
    if (!containerRef.current) return;
    
    // Register Tactus language
    registerTactusLanguage();
    
    // Initialize Monaco with dynamic theme
    const editor = monaco.editor.create(containerRef.current, {
      value: initialValue || '',
      language: 'tactus-lua',
      theme: isDark ? 'tactus-dark' : 'tactus-light',
      automaticLayout: true,
      minimap: {
        enabled: true,
        showSlider: 'always'
      },
      fontSize: 14,
      lineNumbers: 'on',
      roundedSelection: false,
      scrollBeyondLastLine: false,
      readOnly: false,
      cursorStyle: 'line',
      wordWrap: 'on',
      // Disable features that cause async model access during disposal
      quickSuggestions: false,
      inlineSuggest: { enabled: false }
    });
    
    editorRef.current = editor;
    modelRef.current = editor.getModel() || undefined;
    isDisposedRef.current = false;
    
    // Connect LSP client to backend (uses env var or default)
    try {
      lspClient.current = new LSPClient();
      
      // Handle LSP diagnostics (semantic errors)
      lspClient.current.onDiagnostics((diagnostics: LSPDiagnostic[]) => {
        if (isDisposedRef.current) return;
        
        const model = modelRef.current;
        if (model && !model.isDisposed()) {
          const markers = diagnostics.map(diag => ({
            severity: diag.severity === 1 
              ? monaco.MarkerSeverity.Error 
              : monaco.MarkerSeverity.Warning,
            startLineNumber: diag.range.start.line + 1,
            startColumn: diag.range.start.character + 1,
            endLineNumber: diag.range.end.line + 1,
            endColumn: diag.range.end.character + 1,
            message: diag.message,
            source: 'tactus-lsp'
          }));
          
          monaco.editor.setModelMarkers(model, 'tactus-semantic', markers);
        }
      });
      
      // Send initial document
      const uri = filePath ? `file:///${filePath}` : 'file:///untitled.tac';
      currentFileUri.current = uri;
      lspClient.current.didOpen(uri, initialValue);
      setLspConnected(true);
    } catch (error) {
      console.warn('LSP client connection failed, running in offline mode:', error);
      setLspConnected(false);
    }
    
    // On content change: hybrid validation
    editor.onDidChangeModelContent(() => {
      if (isDisposedRef.current || !editorRef.current) return;
      
      const code = editorRef.current.getValue();
      
      // Notify parent
      if (onValueChangeRef.current) {
        onValueChangeRef.current(code);
      }
      
      // Layer 1: Instant TypeScript validation (< 10ms)
      try {
        const syntaxResult = tsValidator.current.validate(code, 'quick');
        const model = modelRef.current;
        
        if (model && !model.isDisposed()) {
          // Show syntax errors immediately
          const markers = syntaxResult.errors.map(err => ({
            severity: monaco.MarkerSeverity.Error,
            startLineNumber: err.location?.[0] || 1,
            startColumn: err.location?.[1] || 1,
            endLineNumber: err.location?.[0] || 1,
            endColumn: (err.location?.[1] || 1) + 10,
            message: err.message,
            source: 'tactus-syntax'
          }));
          
          if (markers.length > 0) {
            console.log('Syntax errors found:', markers);
          }
          
          monaco.editor.setModelMarkers(model, 'tactus-syntax', markers);
        }
      } catch (error) {
        console.error('TypeScript validation error:', error);
      }
      
      // Layer 2: Debounced LSP validation (semantic, 300ms)
      if (lspClient.current && lspConnected && !isDisposedRef.current) {
        clearTimeout(lspTimer.current);
        lspTimer.current = setTimeout(() => {
          if (!isDisposedRef.current) {
            lspClient.current?.didChange(code);
          }
        }, 300);
      }
    });
    
    // Cleanup
    return () => {
      // Set disposed flag first to prevent new operations
      isDisposedRef.current = true;
      
      // Clear any pending timers
      if (lspTimer.current) {
        clearTimeout(lspTimer.current);
        lspTimer.current = undefined;
      }
      
      // Disconnect LSP client
      if (lspClient.current) {
        try {
          lspClient.current.didClose();
          lspClient.current.disconnect();
        } catch (e) {
          // Ignore errors during cleanup
        }
        lspClient.current = undefined;
      }
      
      // Clear markers before disposing (check both model and editor)
      try {
        const model = modelRef.current;
        if (model && !model.isDisposed()) {
          monaco.editor.setModelMarkers(model, 'tactus-syntax', []);
          monaco.editor.setModelMarkers(model, 'tactus-semantic', []);
        }
      } catch (e) {
        // Model might already be disposed, ignore
      }
      
      // Dispose editor (this also disposes the model)
      try {
        if (editorRef.current) {
          editorRef.current.dispose();
          editorRef.current = undefined;
        }
      } catch (e) {
        // Ignore errors during disposal
      }
      
      modelRef.current = undefined;
    };
  }, []); // Empty deps - only run once on mount
  
  return (
    <div ref={containerRef} style={{ height: '100%' }} />
  );
});

Editor.displayName = 'Editor';












