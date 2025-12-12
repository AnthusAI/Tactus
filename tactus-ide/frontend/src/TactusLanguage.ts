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
  
  // Theme customization for DSL keywords
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
    colors: {}
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







