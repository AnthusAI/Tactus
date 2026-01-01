# Development Mode with Hot Reload

## The Problem
`tactus ide` serves pre-built files from `dist/`, so you need to rebuild after every change.

## The Solution
Run the backend and frontend separately for hot module replacement (HMR).

### Terminal 1: Backend Only
```bash
cd /Users/ryan.porter/Projects/Tactus
python -m tactus.ide.server
```

Or use Flask directly:
```bash
cd /Users/ryan.porter/Projects/Tactus
FLASK_APP=tactus/ide/server.py flask run --port 5001
```

### Terminal 2: Frontend with Vite HMR
```bash
cd /Users/ryan.porter/Projects/Tactus/tactus-ide/frontend
npm run dev
```

This starts Vite dev server on http://localhost:3000 with:
- ✨ Instant hot module replacement
- 🔥 Changes appear immediately (no rebuild)
- 🚀 Fast refresh for React components

### How It Works
- Frontend (port 3000): Vite dev server with HMR
- Backend (port 5001): Flask API server
- Vite proxies `/api/*` requests to Flask (configured in `vite.config.ts`)

### Benefits
- Edit `src/App.tsx` → see changes instantly
- Edit `src/components/*` → hot reload
- Edit backend `server.py` → restart Flask only
- No `npm run build` needed during development

## Quick Start Script

Create `dev.sh` in project root:
```bash
#!/bin/bash
# Start backend and frontend in development mode

# Start backend in background
cd /Users/ryan.porter/Projects/Tactus
python -m tactus.ide.server &
BACKEND_PID=$!

# Start frontend
cd tactus-ide/frontend
npm run dev

# Cleanup on exit
trap "kill $BACKEND_PID" EXIT
```

Then:
```bash
chmod +x dev.sh
./dev.sh
```

## Current Setup vs Dev Mode

| Feature | `tactus ide` | Dev Mode |
|---------|-------------|----------|
| Hot Reload | ❌ No | ✅ Yes |
| Rebuild Required | ✅ Yes | ❌ No |
| Startup Time | Slow (build) | Fast |
| Best For | Testing prod build | Active development |
| Browser Opens | Auto | Manual (http://localhost:3000) |









