# Tactus Desktop Build Guide

## Quick Build Commands

### Local Development Builds (Mac)

```bash
cd tactus-desktop

# Build everything and package for Mac
npm run build:all && npm run package:mac

# Just rebuild backend (if you changed Python code)
npm run build:backend

# Just rebuild frontend (if you changed React code)
npm run build:frontend
```

### Build All Three Platforms Locally (Mac)

```bash
cd tactus-desktop

# Ensure you're using Python 3.11+ from conda
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate py311

# Build everything
npm run build:frontend  # React frontend
npm run build:backend   # Python backend with PyInstaller
npm run build           # TypeScript compilation

# Package for all platforms
npx electron-builder --mac --linux --win
```

**Output:** `dist-electron/` will contain:
- `Tactus IDE-0.1.0-mac.dmg` (macOS)
- `Tactus IDE-0.1.0-arm64.AppImage` (Linux)
- `Tactus IDE-Setup-0.1.0.exe` (Windows)

## Automated Release Workflow with Semantic Release

The repository uses **semantic-release** to automatically version, build, and publish releases. Desktop apps are built as part of the standard release process in `.github/workflows/release.yml`.

### How Releases Work

Releases are triggered automatically when you push commits to the `main` branch using **conventional commit messages**:

```bash
# Examples of conventional commits
git commit -m "feat: add new feature"           # Minor version bump (0.1.0 → 0.2.0)
git commit -m "fix: fix critical bug"           # Patch version bump (0.1.0 → 0.1.1)
git commit -m "feat!: breaking API change"      # Major version bump (0.1.0 → 1.0.0)
git commit -m "docs: update documentation"      # No version bump
git commit -m "chore: update dependencies"      # No version bump
```

### Release Process

1. **Make your changes** and commit with conventional commit messages
2. **Push to main branch**:
   ```bash
   git push origin main
   ```

3. **GitHub Actions automatically**:
   - Runs quality checks (ruff, black, pytest, behave)
   - If all tests pass, semantic-release determines new version
   - Publishes Python package to PyPI
   - **Builds desktop apps** for Mac, Windows, and Linux in parallel
   - Attaches desktop installers to GitHub Release

### What Gets Published

Each release includes:
- **Python package** on PyPI: `pip install tactus=={version}`
- **Desktop installers** on GitHub Releases:
  - `Tactus IDE-{version}-mac.dmg` (macOS)
  - `Tactus IDE-{version}-arm64.AppImage` (Linux)
  - `Tactus IDE-Setup-{version}.exe` (Windows)

**Access releases at**: `https://github.com/your-org/Tactus/releases/`

## Important: Python Version Requirement

The backend **must** be built with Python 3.11+ (not system Python). The build scripts will fail if using the wrong Python version.

**Correct setup:**
```bash
# Use conda environment
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate py311
python --version  # Should show Python 3.11.x
```

## Icon Management

Icons are generated from `../Tactus-web/assets/icon.png` using the script:

```bash
cd tactus-desktop
./scripts/generate-icons.sh
```

This creates:
- `resources/app-icon.icns` (macOS)
- `resources/app-icon.ico` (Windows)
- `resources/app-icon.png` (Linux)

To update icons, replace the source PNG and re-run the script.

## Troubleshooting

### Backend crashes on startup

**Symptom:** App menu flickers and quits immediately

**Solution:** Check `~/Library/Logs/Tactus IDE/main.log` for errors

Common issues:
- Missing Python modules → Update `tactus_backend.spec` hiddenimports
- Missing data files → Update `tactus_backend.spec` datas section
- Wrong Python version → Use conda py311 environment

### "Cannot find module" errors

Ensure all dependencies are in `tactus_backend.spec`:

```python
hiddenimports=[
    # ... existing imports
    'your_missing_module',
],
```

Then rebuild:
```bash
conda activate py311
npm run build:backend
```

### Large file sizes

Current sizes (~700MB) include:
- Full Python 3.11 runtime
- PyTorch, NumPy, SciPy, and ML dependencies
- Frontend build with Monaco Editor

This is normal for a desktop app bundling a full Python environment.

## Build Artifacts Location

All builds output to: `tactus-desktop/dist-electron/`

**Structure:**
```
dist-electron/
├── Tactus IDE-0.1.0-mac.dmg          # macOS installer
├── Tactus IDE-0.1.0-arm64.AppImage   # Linux portable
├── Tactus IDE-Setup-0.1.0.exe        # Windows installer
├── mac-arm64/                        # Unpacked Mac app
├── linux-arm64-unpacked/             # Unpacked Linux app
└── win-arm64-unpacked/               # Unpacked Windows app
```

## Testing Builds

### macOS
```bash
open dist-electron/Tactus\ IDE-0.1.0-mac.dmg
# Drag to Applications, then remove quarantine flag:
xattr -cr "/Applications/Tactus IDE.app"
# Now you can open normally or via right-click → Open
```

**Troubleshooting "damaged" error:** Downloaded DMGs from GitHub Releases may show this error due to macOS Gatekeeper on unsigned apps. Remove the quarantine flag:
```bash
# After downloading from GitHub Releases:
xattr -cr ~/Downloads/Tactus.IDE-*.dmg
open ~/Downloads/Tactus.IDE-*.dmg
```

### Linux
```bash
chmod +x dist-electron/Tactus\ IDE-0.1.0-arm64.AppImage
./dist-electron/Tactus\ IDE-0.1.0-arm64.AppImage
```

### Windows
Run `Tactus IDE-Setup-0.1.0.exe`
- Click "More info" → "Run anyway" on SmartScreen warning

## Known Limitations

1. **No code signing** - Users see security warnings on first launch
2. **No auto-updates** - Users must manually download new versions
3. **Large file size** - ~700MB due to bundled Python runtime
4. **No file associations** - Can't double-click .tac files to open

These are acceptable for an MVP and can be addressed in future releases.

## Version Management

Version is set in `tactus-desktop/package.json`:

```json
{
  "version": "0.1.0"
}
```

Update with:
```bash
cd tactus-desktop
npm version patch  # 0.1.0 → 0.1.1
npm version minor  # 0.1.1 → 0.2.0
npm version major  # 0.2.0 → 1.0.0
```

Then tag and push to trigger builds.
