# Tactus IDE Troubleshooting Guide

## Quick Diagnostics

### Is the IDE working?

Check these indicators:

1. **Console** - Should be clean, no red errors
2. **Header** - Shows connection status
3. **Typing** - Syntax errors appear instantly
4. **Backend** - Terminal shows "Starting Tactus IDE Backend on port 5001"

---

## Common Issues

### Issue 1: "MonacoEnvironment.getWorkerUrl" Error

**Symptoms:**
```
You must define a function MonacoEnvironment.getWorkerUrl or MonacoEnvironment.getWorker
```

**Status:** ✅ FIXED in latest version

**Verification:**
Check `frontend/src/main.tsx` contains:
```typescript
(self as any).MonacoEnvironment = {
  getWorkerUrl: function (_moduleId: string, label: string) {
    // ... configuration
  }
};
```

**If still occurring:**
1. Clear browser cache
2. Restart frontend: `npm run dev`
3. Hard refresh browser (Cmd+Shift+R)

---

### Issue 2: WebSocket Connection Failed

**Symptoms:**
```
WebSocket connection to 'ws://localhost:5000/socket.io/...' failed
```

**Status:** ✅ FIXED in latest version

**Verification:**
1. Backend should be on port **5001** (not 5000)
2. Check `frontend/src/Editor.tsx` line 53:
   ```typescript
   lspClient.current = new LSPClient('http://localhost:5001');
   ```

**If still occurring:**

**Check 1: Is backend running?**
```bash
lsof -i :5001
```
Should show Python process. If not:
```bash
cd tactus-ide/backend
python app.py
```

**Check 2: Is port correct?**
```bash
grep -r "localhost:5000" tactus-ide/frontend/src/
```
Should return nothing. If it finds anything, update to 5001.

**Check 3: Firewall blocking?**
```bash
curl http://localhost:5001/health
```
Should return: `{"status":"ok","service":"tactus-ide-backend"}`

---

### Issue 3: "Model is disposed!" Error

**Symptoms:**
```
Uncaught (in promise) Error: Model is disposed!
```

**Status:** ✅ FIXED in latest version

**Verification:**
Check `frontend/src/Editor.tsx` contains:
```typescript
const modelRef = useRef<monaco.editor.ITextModel>();
const isDisposedRef = useRef(false);

// And checks like:
if (model && !model.isDisposed()) {
  // ... use model
}
```

**If still occurring:**
1. Check if you're using React Strict Mode (expected behavior in dev)
2. Verify cleanup code runs on unmount
3. Check console for other errors

---

### Issue 4: IDE Shows "Offline Mode"

**Symptoms:**
- Header shows "○ Offline Mode"
- No semantic validation
- Auto-completion limited

**Status:** This is expected behavior when backend is unavailable

**Solution:**

**Step 1: Check if backend is running**
```bash
lsof -i :5001
```

**Step 2: Start backend if needed**
```bash
cd tactus-ide/backend
python app.py
```

**Step 3: Check backend logs**
Look for:
```
Starting Tactus IDE Backend on port 5001
```

**Step 4: Check for errors**
Common issues:
- Port already in use
- Missing dependencies
- Python version < 3.11

**Step 5: Verify connection**
```bash
curl http://localhost:5001/health
```

**Step 6: Check browser console**
Should see:
```
LSP client connected
```

---

### Issue 5: Frontend Won't Start

**Symptoms:**
```bash
npm run dev
# Error or nothing happens
```

**Solution:**

**Step 1: Check Node version**
```bash
node --version  # Should be 18+
```

**Step 2: Reinstall dependencies**
```bash
cd tactus-ide/frontend
rm -rf node_modules package-lock.json
npm install
```

**Step 3: Check for port conflict**
```bash
lsof -i :3000
```
If something is using port 3000:
```bash
# Kill the process
lsof -ti :3000 | xargs kill

# Or use different port
npm run dev -- --port 3001
```

**Step 4: Check Vite config**
Verify `vite.config.ts`:
```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true
      }
    }
  }
});
```

---

### Issue 6: Backend Won't Start

**Symptoms:**
```bash
python app.py
# Error or crash
```

**Solution:**

**Step 1: Check Python version**
```bash
python --version  # Should be 3.11+
```

**Step 2: Check dependencies**
```bash
cd tactus-ide/backend
pip install -r requirements.txt
```

**Step 3: Check for port conflict**
```bash
lsof -i :5001
```
If port is in use:
```bash
# Kill the process
lsof -ti :5001 | xargs kill

# Or use different port
PORT=5002 python app.py
```

**Step 4: Check imports**
```bash
python -c "from lsp_server import LSPServer; print('OK')"
```

**Step 5: Check Tactus installation**
```bash
python -c "from tactus.validation import TactusValidator; print('OK')"
```

---

## Diagnostic Commands

### Check All Services

```bash
# Backend health
curl http://localhost:5001/health

# Frontend running
curl http://localhost:3000

# WebSocket connection
wscat -c ws://localhost:5001/socket.io/?EIO=4&transport=websocket
```

### Check Ports

```bash
# All ports in use
lsof -i -P | grep LISTEN

# Specific ports
lsof -i :3000  # Frontend
lsof -i :5001  # Backend
```

### Check Processes

```bash
# Python processes
ps aux | grep python

# Node processes
ps aux | grep node
```

### Check Logs

```bash
# Backend logs (if running in terminal)
# Look for errors in the terminal where you ran `python app.py`

# Frontend logs
# Look in browser console (F12)
```

---

## Clean Restart

If all else fails, do a clean restart:

```bash
# Stop everything
pkill -f "python app.py"
pkill -f "npm run dev"

# Clean frontend
cd tactus-ide/frontend
rm -rf node_modules package-lock.json
npm install

# Clean backend
cd ../backend
pip install -r requirements.txt --force-reinstall

# Start fresh
cd ..
./start-dev.sh
```

---

## Still Having Issues?

1. **Check browser console** (F12) for errors
2. **Check backend terminal** for Python errors
3. **Check frontend terminal** for build errors
4. **Verify all fixes applied** - see FIXES_APPLIED.md
5. **Check file modifications** - ensure all changes are present

### File Checklist

- [ ] `frontend/src/main.tsx` - Monaco environment configured
- [ ] `frontend/src/Editor.tsx` - Port 5001, lifecycle management
- [ ] `frontend/src/LSPClient.ts` - Connection error handling
- [ ] `backend/app.py` - Port 5001

### Version Check

```bash
# Frontend
cd tactus-ide/frontend
grep "localhost:5001" src/Editor.tsx  # Should find it

# Backend
cd ../backend
grep "PORT=5001" app.py  # Should find it
```

---

## Getting Help

If you're still stuck:

1. **Gather information:**
   - Browser console output
   - Backend terminal output
   - Frontend terminal output
   - Node version: `node --version`
   - Python version: `python --version`

2. **Check documentation:**
   - README.md - Full documentation
   - FIXES.md - Technical details
   - FIXES_APPLIED.md - What was fixed

3. **Review recent changes:**
   - CHANGELOG.md - Version history
   - Git history: `git log --oneline`

---

## Prevention

To avoid issues in the future:

1. **Always use the startup script:**
   ```bash
   ./start-dev.sh
   ```

2. **Check status before starting:**
   ```bash
   lsof -i :3000 :5001
   ```

3. **Keep dependencies updated:**
   ```bash
   # Frontend
   cd frontend && npm update
   
   # Backend
   cd backend && pip install -r requirements.txt --upgrade
   ```

4. **Monitor console:**
   - Keep browser console open (F12)
   - Watch backend terminal for errors
   - Check frontend terminal for warnings

---

**Last Updated:** 2025-12-11  
**Version:** 1.0.0











