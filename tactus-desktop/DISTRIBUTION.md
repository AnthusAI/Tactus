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

## Alternative Distribution Methods (RESEARCHED)

### 1. **Homebrew Cask - BEST SOLUTION**
**Most popular method for unsigned Electron apps. Homebrew handles quarantine automatically.**

Used by: VSCodium, Motrix, MarkText, Kap, FreeTube, PicGo, YesPlayMusic, and many others.

**Advantages:**
- ✅ No manual quarantine removal needed
- ✅ Automatic updates through Homebrew
- ✅ Trusted by developer community
- ✅ No code signing required
- ✅ Users already familiar with `brew install`

**How to Submit:**
1. Create a Cask formula in homebrew/homebrew-cask repository
2. Formula references the DMG from GitHub Releases
3. Homebrew team reviews and merges
4. Users install with: `brew install --cask tactus-ide`

**Example Apps Successfully Using This:**
- VSCodium (VSCode fork): https://github.com/VSCodium/vscodium
- Motrix (download manager): https://github.com/agalwood/Motrix
- MarkText (markdown editor): https://github.com/marktext/marktext

### 2. **Provide Both DMG and ZIP**
Research shows successful apps offer both formats:
- **DMG**: More professional, better UX, drag-to-install
- **ZIP**: Simpler, some users report fewer issues
- Both still trigger quarantine, but choice is good UX

**Examples:**
- draw.io desktop offers both
- VSCodium provides both formats

### 2. **Self-Hosted Downloads with Instructions**
Host the DMG on your own server with clear installation instructions:
- Removes GitHub's automatic quarantine flags
- More control over download experience
- Can show installation instructions before download

### 3. **Real-World Examples of Unsigned Distribution**

**massCode** (most transparent example):
- Repository: https://github.com/massCodeIO/massCode
- Explicitly ships unsigned starting v3.8.0 (dev couldn't afford Apple cert)
- Documents three workarounds in README
- Discussion: https://github.com/massCodeIO/massCode/discussions/413

**YouTube Music (th-ch/youtube-music)**:
- electron-builder config uses `identity: null` to explicitly disable signing
- Ships DMG for both x64 and arm64
- Config: https://github.com/th-ch/youtube-music/blob/master/electron-builder.yml

**MarkText**:
- Repository: https://github.com/marktext/marktext
- Multiple issues (#3889, #3004, #2983) document user workarounds
- Users share solution: `xattr -dr com.apple.quarantine /Applications/MarkText.app/`

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

## Recommended Configuration

Based on research of successful unsigned Electron apps, here's the optimal electron-builder configuration:

```json
{
  "mac": {
    "target": [
      {
        "target": "dmg",
        "arch": ["x64", "arm64"]
      },
      {
        "target": "zip",
        "arch": ["x64", "arm64"]
      }
    ],
    "identity": null,
    "hardenedRuntime": false,
    "gatekeeperAssess": false,
    "category": "public.app-category.developer-tools"
  }
}
```

**Key settings for unsigned builds:**
- `identity: null` - Explicitly disables code signing (recommended by electron-builder maintainers)
- `hardenedRuntime: false` - Not needed without signing
- `gatekeeperAssess: false` - Already set in our config
- Provide both DMG and ZIP - Users can choose which works better

## Immediate Action Items

1. **Update electron-builder config** to add `identity: null` and ZIP target
2. **Submit to Homebrew Cask** - This is the PRIMARY recommended distribution method
3. **Update README** with System Settings method (Option 1) as the easiest solution
4. **Test both DMG and ZIP** to see if either has fewer issues

## Homebrew Cask Submission

Priority: HIGH - This solves the distribution problem for macOS users.

**Steps:**
1. Ensure releases have stable URLs (already done via GitHub Releases)
2. Create Cask formula in homebrew/homebrew-cask
3. Formula example:
```ruby
cask "tactus-ide" do
  version "0.32.2"
  sha256 "..." # calculate with: shasum -a 256 Tactus*.dmg

  url "https://github.com/AnthusAI/Tactus/releases/download/v#{version}/Tactus.IDE-#{version}-mac.dmg"
  name "Tactus IDE"
  desc "IDE for Tactus workflow automation"
  homepage "https://github.com/AnthusAI/Tactus"

  app "Tactus IDE.app"
end
```
