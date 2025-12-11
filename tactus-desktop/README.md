# Tactus IDE - Desktop Application

Electron desktop application for Tactus IDE (Flask backend + React/Monaco frontend).

## Quick Start

### Development Mode

```bash
# Install dependencies
npm install

# Run in development mode (uses system tactus command)
npm run dev
```

### Build for Production

```bash
# Build everything (frontend + backend + Electron)
npm run build:all

# Package for current platform
npm run package:mac     # macOS
npm run package:win     # Windows
npm run package:linux   # Linux
npm run package:all     # All platforms
```

## Architecture

- **Electron Main Process**: Spawns `tactus ide --no-browser` command
- **Backend**: Flask server with LSP support (port auto-detected)
- **Frontend**: React + Monaco Editor (served by backend)
- **Bundling**: PyInstaller for Python, electron-builder for installers

## Requirements

- Node.js 18+
- Python 3.11+ (must be active in your shell)
- PyInstaller (for building backend)
- Tactus package installed (`pip install -e ..` from project root)

**Important:** Ensure you're using Python 3.11+ before building:
```bash
# If using conda:
conda activate py311

# Or ensure python3 points to 3.11+:
python3 --version  # Should show 3.11 or higher
```

## Build Output

- macOS: `dist-electron/Tactus-IDE-{version}-mac.dmg`
- Windows: `dist-electron/Tactus-IDE-Setup-{version}.exe`
- Linux: `dist-electron/Tactus-IDE-{version}-{arch}.AppImage`

## Unsigned Builds

This MVP does not include code signing. Users will see security warnings:

- **macOS**: Right-click > Open (bypass "unidentified developer")
- **Windows**: "More info" > "Run anyway" (SmartScreen warning)
- **Linux**: No issues with unsigned binaries

## Project Structure

```
tactus-desktop/
├── src/
│   ├── main.ts              # Electron entry point
│   ├── backend-manager.ts   # Manages tactus ide process
│   └── menu.ts              # Native menus
├── preload/
│   └── preload.ts           # IPC bridge
├── backend/
│   └── tactus_backend.spec  # PyInstaller configuration
├── scripts/
│   ├── build-backend.js     # Build Python bundle
│   └── build-frontend.js    # Build React app
└── resources/
    └── app-icon.*           # Platform icons
```

## License

MIT
