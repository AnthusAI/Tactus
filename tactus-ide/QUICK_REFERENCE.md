# Tactus IDE - Quick Reference Card

## 🚀 Start the IDE

```bash
cd tactus-ide
./start-dev.sh
```

Then open: **http://localhost:3000**

---

## ✅ Status: All Working

- ✅ Monaco editor loads correctly
- ✅ Web workers function properly
- ✅ LSP connects successfully
- ✅ No console errors
- ✅ Instant syntax validation
- ✅ Semantic validation (when backend running)
- ✅ Graceful offline mode

---

## 📊 Connection Status

**● LSP Connected** = Backend running, full features  
**○ Offline Mode** = Backend unavailable, syntax only

---

## 🔧 Troubleshooting

### Backend won't start
```bash
cd tactus-ide/backend
pip install -r requirements.txt
python app.py
```

### Frontend won't start
```bash
cd tactus-ide/frontend
npm install
npm run dev
```

### Port conflicts
```bash
lsof -i :3000 :5001  # Check what's using ports
lsof -ti :3000 | xargs kill  # Kill frontend
lsof -ti :5001 | xargs kill  # Kill backend
```

### Clean restart
```bash
pkill -f "python app.py"
pkill -f "npm run dev"
./start-dev.sh
```

---

## 📁 Key Files

### Modified for Fixes
- `frontend/src/main.tsx` - Monaco environment
- `frontend/src/Editor.tsx` - Port + lifecycle
- `frontend/src/LSPClient.ts` - Connection handling

### Documentation
- `FINAL_STATUS.md` - Complete status report
- `SUMMARY.md` - Quick overview
- `TROUBLESHOOTING.md` - Problem solving
- `README.md` - Full documentation

---

## 🎯 Features

### Instant (< 10ms)
- Syntax validation
- Error highlighting
- Works offline

### Semantic (300ms)
- Cross-reference validation
- Context-aware completions
- Hover documentation
- Requires backend

---

## 🔍 Verification

### Check Console
Should see:
```
[vite] connected.
LSP client connected
```

Should NOT see:
- ❌ Monaco environment errors
- ❌ WebSocket connection errors
- ❌ Model disposal errors
- ❌ Worker loading errors

### Check UI
- Header shows connection status
- Editor loads with example code
- Typing shows instant validation
- No red errors in console

---

## 📞 Quick Commands

```bash
# Start everything
./start-dev.sh

# Backend only
cd backend && python app.py

# Frontend only
cd frontend && npm run dev

# Check health
curl http://localhost:5001/health

# Check ports
lsof -i :3000 :5001

# View logs
# Backend: Terminal where python app.py runs
# Frontend: Browser console (F12)
```

---

## 🎓 Learn More

- Architecture: `ARCHITECTURE.md`
- All fixes: `FIXES_APPLIED.md`
- Full guide: `README.md`
- Index: `INDEX.md`

---

**Status:** ✅ Ready for Use  
**Version:** 1.0.0  
**Updated:** 2025-12-11


