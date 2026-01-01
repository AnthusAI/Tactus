# Running Tactus IDE in Electron

## Prerequisites
The Electron app is now built and ready to run!

## Steps to Run

### 1. Stop the browser version (if running)
If you have `tactus ide` running in a terminal, stop it with `Ctrl+C`.

### 2. Start the Electron app
```bash
cd /Users/ryan.porter/Projects/Tactus/tactus-desktop
npm run dev
```

This will:
- Start the Electron desktop application
- The app will automatically start the backend server
- The app will load the frontend from the Vite dev server
- A native window will open with the IDE

## What's Different in Electron

### Native Features
- **Native File Picker**: File → Open Folder uses macOS native dialog
- **OS Menu Bar**: Full menu integration with keyboard shortcuts
- **Window Management**: Native minimize, maximize, close
- **Desktop Icon**: Appears in your dock/taskbar

### Menu Bar
The Electron version has a native OS menu bar with:
- **File**: Open Folder (Cmd+O), Save (Cmd+S), Save As (Cmd+Shift+S)
- **Edit**: Standard edit commands (Undo, Redo, Cut, Copy, Paste)
- **View**: Toggle File Tree (Cmd+B), Toggle Chat (Cmd+Shift+B), Toggle Metrics (Cmd+J)
- **Run**: Validate (Cmd+Shift+V), Validate and Run (Cmd+Shift+R), Run (Cmd+R)
- **Window**: Standard window controls

### Command Dispatch
All menu items dispatch to the same command registry as the in-app menubar, ensuring consistent behavior.

## Troubleshooting

### Port Already in Use
If you see port conflicts, make sure the browser version (`tactus ide`) is stopped.

### Backend Won't Start
The Electron app expects `tactus` CLI to be in your PATH. Verify with:
```bash
which tactus
```

### Frontend Not Loading
The Electron app uses the Vite dev server. If it fails to start, check:
```bash
cd ../tactus-ide/frontend
npm run dev
```

## Development vs Production

### Development (Current)
- `npm run dev` - Runs with Vite dev server for hot reload
- Backend runs as subprocess via `tactus ide --no-browser`
- Best for development and testing

### Production (Future)
- `npm run package:mac` - Creates standalone .dmg installer
- Bundles frontend build (from `dist/`)
- Bundles backend executable
- No dependencies needed on user's machine

## Next Steps

Once the Electron app is running:
1. Use File → Open Folder (or Cmd+O) - this will show a **native folder picker**
2. Select a folder with `.tac` files
3. Navigate files in the tree
4. Edit, validate, and run procedures
5. All keyboard shortcuts work through the OS menu

The Electron version provides the full native desktop experience!









