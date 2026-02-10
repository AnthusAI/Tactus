# Tactus for Visual Studio Code

Full language support for the Tactus AI workflow language.

## Features

### Basic Features (Always Available)

- **Syntax Highlighting**: Full syntax highlighting for `.tac` files including:
  - Tactus DSL keywords (`Agent`, `Procedure`, `Task`, `Tool`, etc.)
  - Field builders (`field.string`, `field.number`, `field.boolean`, etc.)
  - Lua base language support
  - Comments and strings with proper escape sequences
  - String template interpolation highlighting

- **Editor Features**:
  - Comment toggling with `Cmd+/` (Mac) or `Ctrl+/` (Windows/Linux)
  - Auto-closing brackets, quotes, and braces
  - Smart indentation
  - Code folding
  - Bracket matching

### Enhanced Features (With LSP Server)

Install `tactus-lsp-server` for advanced code intelligence:

- **Real-time Validation**: Catch errors as you type with instant diagnostics
- **Intelligent Code Completion**: Context-aware suggestions for DSL keywords, agents, and tools
- **Hover Documentation**: See agent/tool configuration without jumping to definition
- **Semantic Highlighting**: Colors based on semantic meaning (agents vs tools vs procedures)
- **Signature Help**: Parameter hints for DSL functions

## Installation

### Basic Installation (Syntax Highlighting Only)

1. Download the `.vsix` file
2. Open VSCode
3. Go to Extensions (Cmd+Shift+X or Ctrl+Shift+X)
4. Click the "..." menu at the top of the Extensions panel
5. Select "Install from VSIX..."
6. Choose the downloaded `.vsix` file

### Full Installation (With LSP Features)

1. Install Python 3.9 or higher
2. Install the Tactus LSP server:
   ```bash
   pip install tactus-lsp-server
   ```
3. Install the VSCode extension (as above)
4. Open a `.tac` file - LSP features will activate automatically

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/AnthusAI/Tactus
   cd Tactus/tactus-vscode
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Package the extension:
   ```bash
   npm run package
   ```

4. Install the generated `.vsix` file:
   ```bash
   code --install-extension tactus-0.1.0.vsix
   ```

## Supported Syntax

### DSL Keywords

- **Core**: `Agent`, `Model`, `Procedure`, `Task`, `Tool`, `Toolset`
- **Context**: `Context`, `Prompt`, `Human`, `Log`, `State`
- **Testing**: `Specification`, `Specifications`, `Step`
- **Evaluation**: `Evaluation`, `Evaluations`
- **Configuration**: `name`, `version`, `description`, `input`, `output`
- **Advanced**: `IncludeTasks`, `Hitl`, `File`, `Session`, `Retry`

### Field Builders

```lua
field.string{required = true, description = "..."}
field.number{default = 10}
field.boolean{required = false}
field.array{description = "..."}
field.object{description = "..."}
```

### Example

```lua
-- Import tools
local done = require("tactus.tools.done")

-- Define agent
worker = Agent {
  provider = "openai",
  model = "gpt-4o",
  system_prompt = "You are helpful",
  tools = {done}
}

-- Define workflow
Procedure {
  input = {
    task = field.string{required = true}
  },
  output = {
    result = field.string{required = true}
  },
  function(input)
    repeat
      worker()
    until done.called()
    return {result = Tool.last_result("done")}
  end
}
```

## About Tactus

Tactus is a Lua-based DSL for building AI agent workflows. It extends Lua with high-level primitives for:

- Defining LLM-powered agents
- Creating structured workflows with I/O schemas
- Tool integration and agent-tool interactions
- Human-in-the-loop workflows
- BDD-style testing with Gherkin syntax
- Automatic checkpointing and durability

Learn more at [https://github.com/AnthusAI/Tactus](https://github.com/AnthusAI/Tactus)

## Development

To test the extension during development:

1. Open the `tactus-vscode` folder in VSCode
2. Press F5 to launch the Extension Development Host
3. Open a `.tac` file to see syntax highlighting

## Contributing

Contributions are welcome! Please see the main [Tactus repository](https://github.com/AnthusAI/Tactus) for contribution guidelines.

## License

MIT License - see [LICENSE](../LICENSE) file in the root of the repository.
