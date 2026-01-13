/**
 * YAML Code Editor component using Monaco Editor.
 */

import React, { useRef, useEffect } from 'react';
import * as monaco from 'monaco-editor';
import { validateYaml } from '../../utils/yamlSync';

interface YamlCodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  errors?: string[];
  readOnly?: boolean;
}

export function YamlCodeEditor({ value, onChange, errors, readOnly = false }: YamlCodeEditorProps) {
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Create Monaco editor
    const editor = monaco.editor.create(containerRef.current, {
      value,
      language: 'yaml',
      theme: document.documentElement.classList.contains('dark')
        ? 'vs-dark'
        : 'vs-light',
      minimap: { enabled: false },
      fontSize: 13,
      lineNumbers: 'on',
      scrollBeyondLastLine: false,
      automaticLayout: true,
      tabSize: 2,
      readOnly,
    });

    editorRef.current = editor;

    // Listen for changes
    const disposable = editor.onDidChangeModelContent(() => {
      const newValue = editor.getValue();
      onChange(newValue);

      // Validate YAML and show markers
      const error = validateYaml(newValue);
      if (error) {
        const model = editor.getModel();
        if (model) {
          monaco.editor.setModelMarkers(model, 'yaml', [
            {
              severity: monaco.MarkerSeverity.Error,
              message: error,
              startLineNumber: 1,
              startColumn: 1,
              endLineNumber: 1,
              endColumn: 1,
            },
          ]);
        }
      } else {
        const model = editor.getModel();
        if (model) {
          monaco.editor.setModelMarkers(model, 'yaml', []);
        }
      }
    });

    // Cleanup
    return () => {
      disposable.dispose();
      editor.dispose();
    };
  }, []); // Only create editor once

  // Update value when prop changes (but not from our own onChange)
  useEffect(() => {
    if (editorRef.current && editorRef.current.getValue() !== value) {
      editorRef.current.setValue(value);
    }
  }, [value]);

  // Update readOnly when prop changes
  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.updateOptions({ readOnly });
    }
  }, [readOnly]);

  // Update theme when it changes
  useEffect(() => {
    const observer = new MutationObserver(() => {
      if (editorRef.current) {
        const isDark = document.documentElement.classList.contains('dark');
        monaco.editor.setTheme(isDark ? 'vs-dark' : 'vs-light');
      }
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    });

    return () => observer.disconnect();
  }, []);

  return (
    <div className="h-full flex flex-col">
      {errors && errors.length > 0 && (
        <div className="bg-destructive/10 border-destructive/20 border-b px-4 py-3">
          <div className="text-sm font-medium text-destructive mb-1">Errors:</div>
          <ul className="text-sm text-destructive space-y-1">
            {errors.map((error, i) => (
              <li key={i}>• {error}</li>
            ))}
          </ul>
        </div>
      )}
      <div ref={containerRef} className="flex-1 overflow-hidden" />
    </div>
  );
}
