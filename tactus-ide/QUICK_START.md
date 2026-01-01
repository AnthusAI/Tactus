# Tactus IDE - Quick Start Guide

## Installation

### 1. Install Frontend Dependencies
```bash
cd tactus-ide/frontend
npm install
```

### 2. Install Backend Dependencies
Backend dependencies should already be installed with the main Tactus package.

## Running the IDE

### Browser Mode (Development)
```bash
# From the project root
tactus ide

# This will start:
# - Backend server on http://localhost:5001
# - Frontend dev server on http://localhost:3000
# - Open your browser to http://localhost:3000
```

### Electron Desktop App (Development)
```bash
# Build the desktop app
cd tactus-desktop
npm install
npm run build

# Run the desktop app
npm start
```

## First Steps

### 1. Open a Workspace Folder
- **Electron**: File → Open Folder... (or Cmd+O)
- **Browser**: File → Open Folder... → Enter absolute path

The workspace folder should contain your `.tac` procedure files.

### 2. Navigate Files
- Use the left sidebar file tree to browse your workspace
- Click any file to open it in the Monaco editor
- `.tac` files are marked with a blue code icon

### 3. Edit and Save
- Edit files in the Monaco editor
- Save with Cmd+S (or File → Save)
- Unsaved changes are indicated in the top bar

### 4. Validate Your Code
Click the **Validate** button to check your procedure for errors:
- Syntax errors are shown immediately (TypeScript parser)
- Semantic errors appear after ~300ms (Python LSP)
- Results appear in the bottom drawer

### 5. Run Your Procedure
Three options:
- **Validate**: Check for errors only
- **Validate & Run**: Validate first, then run if valid
- **Run**: Execute immediately (Cmd+R)

Output appears in the bottom drawer with:
- Exit code
- Standard output
- Standard error
- Success/failure indicator

### 6. Use the Chat (Coming Soon)
The right sidebar contains a chat interface for AI assistance:
- Currently a placeholder
- Will integrate with AI backends in future updates

## Keyboard Shortcuts

### File Operations
- `Cmd+O` - Open Folder
- `Cmd+S` - Save File
- `Cmd+Shift+S` - Save As (coming soon)

### View Toggles
- `Cmd+B` - Toggle File Tree
- `Cmd+Shift+B` - Toggle Chat Sidebar
- `Cmd+J` - Toggle Metrics Drawer

### Run Operations
- `Cmd+Shift+V` - Validate
- `Cmd+Shift+R` - Validate and Run
- `Cmd+R` - Run

### Editor (Standard Monaco)
- `Cmd+F` - Find
- `Cmd+H` - Replace
- `Cmd+/` - Toggle Comment
- `Cmd+Z` - Undo
- `Cmd+Shift+Z` - Redo

## UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Tactus IDE | File Edit View Run | workspace • file.lua      │
├─────────────────────────────────────────────────────────────┤
│ [Validate] [Validate & Run] [Run] ✓ Success                 │
├──────────┬──────────────────────────────────┬───────────────┤
│          │                                  │               │
│  Files   │        Monaco Editor             │     Chat      │
│          │                                  │               │
│  tree    │        (your code here)          │   messages    │
│          │                                  │               │
│  [<]     │                                  │     [>]       │
│          │                                  │               │
├──────────┴──────────────────────────────────┴───────────────┤
│ Output / Metrics Drawer                              [v]    │
│ Validation: ✓ Valid                                         │
│ Run Result: ✓ Success (exit code: 0)                        │
│ stdout: Hello, Tactus!                                      │
└─────────────────────────────────────────────────────────────┘
```

## Workspace Security

The IDE restricts all file operations to your selected workspace folder:
- Cannot access files outside the workspace
- Path traversal attacks are prevented
- Safe for working with untrusted code

## Troubleshooting

### Backend Won't Start
```bash
# Check if port 5001 is in use
lsof -i :5001

# Try a different port
PORT=5002 tactus ide
```

### Frontend Won't Connect
- Ensure backend is running on http://localhost:5001
- Check browser console for errors
- Verify `/api/health` returns OK: `curl http://localhost:5001/health`

### LSP Not Working
- Check backend logs for errors
- Verify WebSocket connection in browser DevTools
- LSP runs in "offline mode" if connection fails (syntax validation still works)

### Validation Fails
- Ensure your `.tac` file has required fields: `name()`, `version()`, `procedure()`
- Check the Output drawer for specific error messages
- Refer to SPECIFICATION.md for DSL syntax

### Run Fails
- Ensure `tactus` CLI is in your PATH
- Check that the workspace folder is set correctly
- Verify the procedure file is saved before running
- Check Output drawer for stderr messages

## Development Tips

### Hot Reload
- Frontend changes reload automatically (Vite HMR)
- Backend changes require restart

### Debug Mode
- Open DevTools in browser (Cmd+Option+I)
- In Electron: View → Toggle Developer Tools
- Check Console tab for errors
- Check Network tab for API calls

### Custom Themes
Edit `tactus-ide/frontend/src/index.css` to customize colors:
- Light mode: `:root` variables
- Dark mode: `.dark` variables

## Next Steps

1. Try the example procedures in `examples/`
2. Create your own `.tac` files
3. Explore the command registry in `src/commands/registry.ts`
4. Customize the UI components in `src/components/`
5. Read the full specification in `SPECIFICATION.md`

## Getting Help

- Check `IDE_OVERHAUL_SUMMARY.md` for implementation details
- Read `SPECIFICATION.md` for DSL syntax
- See `IMPLEMENTATION.md` for feature status
- Report issues on GitHub (when available)









