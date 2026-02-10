# Change Log

All notable changes to the Tactus VSCode extension will be documented in this file.

## [0.1.0] - 2026-02-05

### Added
- Initial release of Tactus VSCode extension
- **Syntax Highlighting** for `.tac` files
  - Support for all Tactus DSL keywords (Agent, Procedure, Task, Tool, etc.)
  - Field builder syntax highlighting (field.string, field.number, etc.)
  - Lua base language support
  - String template interpolation highlighting
- **Editor Features**
  - Comment toggling and formatting
  - Auto-closing brackets, quotes, and braces
  - Smart indentation rules
  - Code folding support
  - Bracket matching
- **LSP Integration** (requires tactus-lsp-server)
  - Real-time validation with diagnostics
  - Intelligent code completion
  - Hover documentation for agents, tools, and procedures
  - Signature help for DSL functions
  - Auto-detection of Python environment
  - Graceful fallback to syntax highlighting if LSP not available
