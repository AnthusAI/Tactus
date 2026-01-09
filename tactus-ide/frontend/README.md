# Tactus IDE Frontend

React-based frontend for the Tactus IDE, using Monaco Editor with hybrid validation.

## Architecture

### Hybrid Validation Approach

**Layer 1: TypeScript Parser (Instant)**
- ANTLR-generated parser in `src/validation/`
- Validates syntax as you type (< 10ms)
- Works offline, no backend needed
- Shows red squiggles immediately

**Layer 2: Python LSP (Semantic)**
- Connects to Flask backend via WebSocket
- Provides intelligent completions
- Hover documentation
- Signature help
- Cross-reference validation

### Components

- **Monaco Editor**: VS Code's editor component
- **LSP Client**: Communicates with Python LSP backend
- **TypeScript Parser**: ANTLR-generated parser for client-side validation
- **React**: UI framework
- **Electron-ready**: Can be packaged as desktop app

## Development

```bash
npm install
npm run dev   # Start development server
npm test      # Run tests (includes parser tests)
npm run build # Production build
npm run demo  # Run parser demo
```

## TypeScript Parser

The frontend includes an ANTLR-generated TypeScript parser in `src/validation/`.

**Generated from:** `../../tactus/validation/grammar/LuaLexer.g4` and `LuaParser.g4`

**Purpose:**
- Instant syntax validation (no backend needed)
- Offline editing support
- Reduced backend load

**Usage:**
```typescript
import { TactusValidator } from './validation/TactusValidator';

const validator = new TactusValidator();
const result = validator.validate(code, 'quick');

if (!result.valid) {
  // Show syntax errors immediately
}
```

**Test Results:**
```
✓ 12 tests passing
  - Valid Lua syntax parsing
  - Invalid syntax detection
  - Error location reporting
  - DSL function call recognition
  - Parameter extraction
  - Output extraction
  - Agent extraction
  - Example file validation
  - Missing required fields detection
  - Quick vs full validation modes
```

For full LSP features (autocomplete, hover, etc.), the Python backend is required

## IDE Components

### Editor.tsx
Main editor component with hybrid validation:
- Monaco Editor integration
- TypeScript parser for instant syntax validation
- LSP client for semantic intelligence
- Real-time error markers

### LSPClient.ts
WebSocket client for Python LSP backend:
- JSON-RPC 2.0 protocol
- Handles diagnostics, completions, hover
- Automatic reconnection

### TactusLanguage.ts
Monaco language definition:
- Syntax highlighting for Tactus DSL
- Custom theme with DSL keyword highlighting
- Basic completion providers (enhanced by LSP)

## Parser Parity

The TypeScript parser is designed to have **identical behavior** to the Python parser:

| Feature | Python | TypeScript |
|---------|--------|------------|
| Syntax validation | ✅ | ✅ |
| Error detection | ✅ | ✅ |
| DSL extraction | ✅ | ✅ |
| Parameter parsing | ✅ | ✅ |
| Output parsing | ✅ | ✅ |
| Agent parsing | ✅ | ✅ |
| Quick/full modes | ✅ | ✅ |

Both parsers are generated from the same `LuaLexer.g4` and `LuaParser.g4` grammar files.

## Regenerating Parser

If the grammar is updated:

```bash
npm run generate-parser
```

This runs ANTLR to regenerate the TypeScript parser from the grammar.
