# Contributing to Tactus VSCode Extension

Thank you for your interest in contributing to the Tactus VSCode extension!

## Development Setup

### Prerequisites

- Node.js 18+ and npm
- Python 3.9+
- VSCode

### Initial Setup

1. **Clone and install Tactus core:**
   ```bash
   git clone https://github.com/AnthusAI/Tactus
   cd Tactus
   pip install -e .
   ```

2. **Install LSP server for development:**
   ```bash
   cd tactus-lsp-server
   pip install -e .
   cd ..
   ```

3. **Install extension dependencies:**
   ```bash
   cd tactus-vscode
   cd client && npm install && cd ..
   ```

### Development Workflow

#### Testing the Extension

1. **Open extension in VSCode:**
   ```bash
   code tactus-vscode/
   ```

2. **Launch Extension Development Host:**
   - Press `F5` (or Run > Start Debugging)
   - A new VSCode window opens with extension loaded
   - Open any `.tac` file to test

3. **View LSP server logs:**
   - In Extension Development Host, go to Output panel
   - Select "Tactus Language Server" from dropdown

#### Making Changes

**TextMate Grammar (Syntax Highlighting):**
- Edit: `tactus-vscode/syntaxes/tactus.tmLanguage.json`
- Changes apply immediately (reload window)

**LSP Features (Validation, Completions, etc.):**
- Edit: `tactus-lsp-server/tactus_lsp_server/handler.py`
- Restart extension (Ctrl+R in Extension Development Host)

**Extension Client:**
- Edit: `tactus-vscode/client/src/extension.ts`
- Run: `npm run compile`
- Restart extension

### Testing

#### Manual Testing Checklist

Test with these example files:
- `examples/01-basics-hello-world.tac`
- `examples/04-basics-simple-agent.tac`
- `examples/14-feature-per-turn-tools.tac`

Verify:
- [ ] Syntax highlighting works instantly
- [ ] LSP server starts (check Output panel)
- [ ] Validation: Introduce typo, see red squiggle
- [ ] Completions: Type `Ag` + Ctrl+Space → suggests `Agent`
- [ ] Hover: Hover over agent name → shows config
- [ ] Comment toggling: Cmd+/ or Ctrl+/
- [ ] Bracket matching: Click opening `{` → closing `}` highlights

#### Automated Testing

```bash
# Test LSP server
./scripts/test-lsp-server.sh

# Package extension
cd tactus-vscode
npm run package
```

### Submitting Changes

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes
3. Test thoroughly (see checklist above)
4. Commit with clear message: `git commit -m "feat: add X feature"`
5. Push and create pull request

### Project Structure

```
tactus-vscode/
├── package.json                 # Extension manifest
├── language-configuration.json  # Editor features (brackets, comments)
├── syntaxes/
│   └── tactus.tmLanguage.json  # TextMate grammar
└── client/
    ├── package.json             # Client dependencies
    ├── tsconfig.json
    └── src/
        └── extension.ts         # Language client (LSP)

tactus-lsp-server/
├── pyproject.toml               # Python package config
├── tactus_lsp_server/
│   ├── handler.py               # Core LSP logic
│   ├── stdio_server.py          # pygls server
│   └── semantic_tokens.py       # Semantic highlighting
```

### Common Issues

**LSP server won't start:**
- Check Python installation: `python3 --version`
- Check tactus-lsp-server installed: `pip list | grep tactus-lsp`
- Check logs: Output > Tactus Language Server

**Extension not loading:**
- Check VSCode version >= 1.75
- Check `package.json` syntax is valid
- Reload window: Cmd+R (Mac) or Ctrl+R (Windows/Linux)

**Changes not applying:**
- TextMate grammar: Reload window
- LSP changes: Restart extension (Ctrl+R in dev host)
- Client changes: Run `npm run compile` first

### Resources

- [VSCode Extension API](https://code.visualstudio.com/api)
- [Language Server Protocol](https://microsoft.github.io/language-server-protocol/)
- [TextMate Grammars](https://macromates.com/manual/en/language_grammars)
- [pygls Documentation](https://pygls.readthedocs.io/)

## Questions?

Open an issue on GitHub or reach out to the maintainers.
