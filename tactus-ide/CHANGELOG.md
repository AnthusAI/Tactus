# Tactus IDE Changelog

## 2025-12-11 - Bug Fixes and Stability Improvements

### Fixed

#### 1. Monaco Environment Configuration Error
- **Issue**: Console error: "You must define a function MonacoEnvironment.getWorkerUrl or MonacoEnvironment.getWorker"
- **Fix**: Added proper Monaco environment configuration in `main.tsx`
- **Files Changed**: `frontend/src/main.tsx`

#### 2. WebSocket Connection Failure
- **Issue**: WebSocket connection to 'ws://localhost:5000' failed
- **Root Cause**: Editor was connecting to port 5000, but backend runs on port 5001
- **Fix**: Updated LSP client connection URL to use port 5001
- **Files Changed**: `frontend/src/Editor.tsx`

#### 3. Model Disposal Errors
- **Issue**: "Model is disposed!" errors when editor updates
- **Root Cause**: Monaco was accessing disposed models in async callbacks
- **Fix**: 
  - Added `modelRef` and `isDisposedRef` to track model lifecycle
  - Added `model.isDisposed()` checks before all model access
  - Properly clear markers before disposing editor
  - Guard all async operations with disposal checks
- **Files Changed**: `frontend/src/Editor.tsx`

#### 4. LSP Connection Error Handling
- **Issue**: Poor error handling when backend is unavailable
- **Fix**:
  - Added `isConnected` flag to track connection state
  - Added connection error handler
  - Guard all LSP operations with connection checks
  - Reduced reconnection attempts to 5 with 5s timeout
  - Better error logging (warnings instead of errors)
- **Files Changed**: `frontend/src/LSPClient.ts`

### Added

#### Development Tools
- **start-dev.sh**: Convenient script to start both backend and frontend
- **FIXES.md**: Detailed documentation of all fixes applied
- **CHANGELOG.md**: This file

### Improved

#### User Experience
- IDE now gracefully handles backend disconnection
- Connection status shown in UI header
- Offline mode works seamlessly
- No more console errors or warnings

#### Code Quality
- Better lifecycle management
- Proper cleanup on component unmount
- Defensive programming with disposal checks
- Improved error messages

## Testing

All fixes have been tested with:
- ✅ Backend running (full LSP features)
- ✅ Backend stopped (offline mode)
- ✅ Backend restart while IDE is open
- ✅ Multiple editor instances
- ✅ Rapid typing and editing
- ✅ File open/save operations

## Upgrade Notes

No breaking changes. Simply pull the latest code and restart the IDE.

The IDE now requires:
- Backend on port 5001 (was 5000)
- Frontend on port 3000 (unchanged)

Use `./start-dev.sh` for easy startup.












