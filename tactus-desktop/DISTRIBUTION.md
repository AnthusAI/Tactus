# Distribution Notes for Unsigned Electron Apps

## Current Working Solution (v0.32.2+)

The GitHub Actions build **DOES work** - users just need to remove quarantine attributes:

```bash
# Required steps for macOS users:
xattr -cr ~/Downloads/Tactus*.dmg
open ~/Downloads/Tactus*.dmg
xattr -cr "/Applications/Tactus IDE.app"
```

**Verified working:** v0.32.2 DMG launches successfully after removing quarantine.

## The Problem

When users download the DMG from GitHub Releases:
1. GitHub adds `com.apple.provenance` attribute to downloaded files
2. macOS Gatekeeper sees the app isn't code-signed
3. macOS blocks the app with "damaged" error message
4. Even right-clicking and selecting "Open" doesn't work for unsigned DMGs from the internet

## Why Local Builds Work

Local builds don't have quarantine attributes because they weren't downloaded from the internet. That's why testing locally always worked but CI builds appeared broken.

## Alternative Distribution Methods to Research

### 1. **ZIP Instead of DMG**
Some developers report that distributing as ZIP files instead of DMG reduces Gatekeeper friction:
- ZIP files may trigger less aggressive security checks
- Still requires `xattr -cr` but might be easier for users
- electron-builder supports ZIP: change target from `dmg` to `zip`

### 2. **Self-Hosted Downloads with Instructions**
Host the DMG on your own server with clear installation instructions:
- Removes GitHub's automatic quarantine flags
- More control over download experience
- Can show installation instructions before download

### 3. **Ad-Hoc Code Signing (Free)**
macOS allows ad-hoc signing without Apple Developer account:
```bash
codesign --force --deep --sign - "Tactus IDE.app"
```
- Won't pass Gatekeeper, but might reduce "damaged" errors
- Still requires `xattr -cr` for downloaded apps
- Worth testing if it improves UX

### 4. **Notarization Service Alternatives**
Some third-party services offer notarization for a fee (cheaper than $99/year):
- Research if any legitimate services exist
- Would provide proper macOS integration
- Probably not worth it for MVP

### 5. **Homebrew Cask Distribution**
Distribute via Homebrew:
```bash
brew install --cask tactus-ide
```
- Homebrew handles installation and quarantine removal
- Users familiar with dev tools already use Homebrew
- Requires maintaining a Cask formula

### 6. **electron-builder Auto-Update**
Built-in update mechanism that bypasses Gatekeeper:
- After first install (with xattr), updates work seamlessly
- electron-updater package handles this
- Requires hosting update server

## Research TODO

- [ ] Test ZIP distribution vs DMG (does it actually help?)
- [ ] Test ad-hoc code signing (does it reduce errors?)
- [ ] Research how other unsigned Electron apps distribute (VSCode forks, etc.)
- [ ] Look into Homebrew Cask as primary distribution method
- [ ] Check if electron-builder has any built-in solutions
- [ ] Research user experience: how do other indie Electron apps handle this?

## Key Insight from Debugging

**The app itself is perfectly fine.** The binaries are identical between local and CI builds. The only issue is macOS quarantine attributes added during download from GitHub. This is a distribution problem, not a build problem.

## Projects to Study

Look at how these unsigned/indie Electron apps handle distribution:
- Obsidian (before they got signing)
- Various open-source Electron apps on GitHub
- Community forks of popular apps
- Apps distributed via GitHub Releases without signing

## Cost-Benefit Analysis

**Code Signing ($99/year):**
- ✅ Zero friction for users
- ✅ Professional appearance
- ✅ App Store distribution possible
- ❌ $99/year recurring cost
- ❌ Requires maintaining Apple Developer account

**Current Solution (xattr commands):**
- ✅ Free
- ✅ Works perfectly once configured
- ❌ Extra steps for users
- ❌ Looks less professional
- ✅ Fine for developer/power user audience

For an IDE targeting developers, the current solution may be acceptable since the target audience is comfortable with terminal commands.
