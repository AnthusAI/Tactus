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

## Installing Unsigned Builds

This application is not code-signed (requires $99/year Apple Developer Program). Users need to remove macOS quarantine attributes after downloading.

### macOS Installation

**Option 1: Install via Homebrew (Recommended)**
```bash
# Coming soon - Homebrew Cask handles quarantine automatically
brew install --cask tactus-ide
```

**Option 2: System Settings Method (Easiest for Direct Downloads)**

If you see "app is damaged" error after downloading:

1. Try to open the app (it will be blocked)
2. Go to **System Settings → Privacy & Security**
3. Scroll down and click **"Open Anyway"** button
4. Click **"Open"** when the confirmation appears

This is Apple's official method for opening unsigned apps. More info: https://support.apple.com/en-us/102445

**Option 3: Terminal Command (Advanced Users)**
```bash
# Remove quarantine from the DMG first
xattr -cr ~/Downloads/Tactus*.dmg

# Open DMG, drag to Applications, then remove quarantine from app
xattr -cr "/Applications/Tactus IDE.app"
```

**Why this is needed:** macOS Gatekeeper blocks downloaded apps that aren't code-signed with an Apple Developer certificate ($99/year). Despite the "damaged" message, the app is fine - it's a security warning, not actual corruption.

### Windows Installation

- Click "More info" > "Run anyway" when SmartScreen warning appears
- No additional steps needed after that

### Linux Installation

- No issues with unsigned binaries
- Make AppImage executable: `chmod +x Tactus*.AppImage`

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
