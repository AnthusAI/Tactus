/**
 * Tactus DSL language definition for Monaco Editor.
 * 
 * Provides syntax highlighting and basic language features.
 * Enhanced by hybrid validation (TypeScript + LSP).
 */
import * as monaco from 'monaco-editor';

export function registerTactusLanguage() {
  monaco.languages.register({ id: 'tactus-lua' });
  
  // Syntax highlighting
  monaco.languages.setMonarchTokensProvider('tactus-lua', {
    keywords: [
      'function', 'end', 'local', 'return', 'if', 'then', 'else', 
      'for', 'do', 'while', 'repeat', 'until', 'in', 'and', 'or', 'not'
    ],
    dslKeywords: [
      'name', 'version', 'agent', 'procedure', 'parameter',  
      'output', 'default_provider', 'default_model', 'hitl', 'tool'
    ],
    operators: [
      '=', '==', '~=', '<', '>', '<=', '>=', '+', '-', '*', '/', '%', '^', '#', '..'
    ],
    
    tokenizer: {
      root: [
        // DSL keywords (highlight differently)
        [/\b(name|version|agent|procedure|parameter|output|default_provider|default_model|hitl|tool)\b/, 'keyword.dsl'],
        
        // Lua keywords
        [/\b(function|end|local|return|if|then|else|for|do|while|repeat|until|in|and|or|not)\b/, 'keyword'],
        
        // Lua constants
        [/\b(true|false|nil)\b/, 'constant.language'],
        
        // Strings
        [/"([^"\\]|\\.)*$/, 'string.invalid'],
        [/"/, { token: 'string.quote', bracket: '@open', next: '@string' }],
        
        // Comments
        [/--\[\[/, { token: 'comment', next: '@comment' }],
        [/--.*$/, 'comment'],
        
        // Numbers
        [/\d+\.?\d*([eE][-+]?\d+)?/, 'number'],
        [/0[xX][0-9a-fA-F]+/, 'number.hex'],
        
        // Identifiers
        [/[a-zA-Z_]\w*/, 'identifier'],
        
        // Operators
        [/[{}()\[\]]/, '@brackets'],
        [/[<>]=?|~=|==/, 'operator.comparison'],
        [/[+\-*/%^#]/, 'operator.arithmetic'],
        [/\.\./, 'operator.concatenation'],
      ],
      
      string: [
        [/[^\\"]+/, 'string'],
        [/\\./, 'string.escape'],
        [/"/, { token: 'string.quote', bracket: '@close', next: '@pop' }]
      ],
      
      comment: [
        [/[^\]]+/, 'comment'],
        [/\]\]/, { token: 'comment', next: '@pop' }],
        [/[\]]/, 'comment']
      ]
    }
  });
  
  // Light theme for Tactus DSL
  // Colors derived from Tailwind config (index.css light mode variables)
  // --background: 0 0% 100% -> #ffffff
  // --foreground: 222.2 47.4% 15% -> #141f38
  // --primary: 221.2 83.2% 53.3% -> #3b82f6
  // --muted: 210 40% 96.1% -> #f1f5f9
  // --border: 214.3 31.8% 91.4% -> #e2e8f0
  monaco.editor.defineTheme('tactus-light', {
    base: 'vs',
    inherit: true,
    rules: [
      { token: 'keyword.dsl', foreground: 'AF00DB', fontStyle: 'bold' },
      { token: 'comment', foreground: '008000' },
      { token: 'string', foreground: 'A31515' },
      { token: 'number', foreground: '098658' },
      { token: 'keyword', foreground: '0000FF' },
    ],
    colors: {
      'editor.background': '#ffffff',
      'editor.foreground': '#141f38',
      'editorLineNumber.foreground': '#94a3b8',
      'editor.lineHighlightBackground': '#f1f5f920',
      'editorCursor.foreground': '#3b82f6',
      'editor.selectionBackground': '#3b82f640',

      // Minimap configuration
      'minimap.background': '#ffffff',
      'minimapSlider.background': '#3b82f640',
      'minimapSlider.hoverBackground': '#3b82f660',
      'minimapSlider.activeBackground': '#3b82f680',
      'scrollbarSlider.background': '#3b82f620',
      'scrollbarSlider.hoverBackground': '#3b82f640',
      'scrollbarSlider.activeBackground': '#3b82f660',

      // UI Components
      'editorWidget.background': '#ffffff',
      'editorWidget.border': '#e2e8f0',
      'editorSuggestWidget.background': '#ffffff',
      'editorSuggestWidget.border': '#e2e8f0',
      'editorSuggestWidget.selectedBackground': '#f1f5f9',
      'list.hoverBackground': '#f1f5f940',
    }
  });

  // Theme customization for DSL keywords
  // Colors derived from Tailwind config (index.css dark mode variables)
  // --background: 222.2 84% 4.9% -> #020817
  // --foreground: 210 40% 98% -> #f8fafc
  // --primary: 217.2 91.2% 59.8% -> #3b82f6
  // --muted: 217.2 32.6% 17.5% -> #1e293b
  // --border: 217.2 32.6% 17.5% -> #1e293b
  monaco.editor.defineTheme('tactus-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'keyword.dsl', foreground: 'C586C0', fontStyle: 'bold' },
      { token: 'comment', foreground: '6A9955' },
      { token: 'string', foreground: 'CE9178' },
      { token: 'number', foreground: 'B5CEA8' },
      { token: 'keyword', foreground: '569CD6' },
    ],
    colors: {
      'editor.background': '#020817',
      'editor.foreground': '#f8fafc',
      'editorLineNumber.foreground': '#64748b',
      'editor.lineHighlightBackground': '#1e293b40', // Muted with opacity
      'editorCursor.foreground': '#3b82f6', // Primary
      'editor.selectionBackground': '#3b82f640', // Primary with opacity

      // Minimap configuration - make slider visible using primary color
      // Increased opacity for better visibility
      'minimap.background': '#020817',
      'minimapSlider.background': '#3b82f640', // increased from 30 to 40
      'minimapSlider.hoverBackground': '#3b82f660', // increased from 50 to 60
      'minimapSlider.activeBackground': '#3b82f680', // increased from 70 to 80
      'scrollbarSlider.background': '#3b82f620',
      'scrollbarSlider.hoverBackground': '#3b82f640',
      'scrollbarSlider.activeBackground': '#3b82f660',

      // UI Components
      'editorWidget.background': '#020817',
      'editorWidget.border': '#1e293b',
      'editorSuggestWidget.background': '#020817',
      'editorSuggestWidget.border': '#1e293b',
      'editorSuggestWidget.selectedBackground': '#1e293b',
      'list.hoverBackground': '#1e293b40',
    }
  });
  
  // Basic completions (will be enhanced by LSP)
  monaco.languages.registerCompletionItemProvider('tactus-lua', {
    provideCompletionItems: (model, position) => {
      const word = model.getWordUntilPosition(position);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn
      };
      
      const suggestions: monaco.languages.CompletionItem[] = [
        {
          label: 'name',
          kind: monaco.languages.CompletionItemKind.Function,
          insertText: 'name("${1:procedure_name}")',
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: 'Define the procedure name',
          range
        },
        {
          label: 'version',
          kind: monaco.languages.CompletionItemKind.Function,
          insertText: 'version("${1:1.0.0}")',
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: 'Define the procedure version',
          range
        },
        {
          label: 'agent',
          kind: monaco.languages.CompletionItemKind.Function,
          insertText: [
            'agent("${1:agent_name}", {',
            '\tprovider = "${2:openai}",',
            '\tmodel = "${3:gpt-4o}",',
            '\tsystem_prompt = "${4:You are helpful}"',
            '})'
          ].join('\n'),
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: 'Define an agent',
          range
        },
        {
          label: 'parameter',
          kind: monaco.languages.CompletionItemKind.Function,
          insertText: [
            'parameter("${1:param_name}", {',
            '\ttype = "${2:string}",',
            '\trequired = ${3:true},',
            '\tdefault = "${4:default_value}"',
            '})'
          ].join('\n'),
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: 'Define a parameter',
          range
        },
        {
          label: 'output',
          kind: monaco.languages.CompletionItemKind.Function,
          insertText: [
            'output("${1:output_name}", {',
            '\ttype = "${2:string}",',
            '\trequired = ${3:true}',
            '})'
          ].join('\n'),
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: 'Define an output field',
          range
        },
        {
          label: 'procedure',
          kind: monaco.languages.CompletionItemKind.Function,
          insertText: [
            'procedure(function()',
            '\t${1:-- Your code here}',
            '\treturn { success = true }',
            'end)'
          ].join('\n'),
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: 'Define the procedure function',
          range
        }
      ];
      
      return { suggestions };
    }
  });
}












