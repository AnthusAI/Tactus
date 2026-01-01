# Restart Instructions

The IDE overhaul is complete! To see the new UI:

## 1. Stop the current `tactus ide` process
Press `Ctrl+C` in the terminal where `tactus ide` is running.

## 2. Restart the IDE
```bash
tactus ide
```

The browser should open automatically to http://localhost:3000

## What You'll See

The new UI features:
- **Top bar** with Tactus branding, menubar (File/Edit/View/Run), and notification icons
- **File tree** on the left (collapsible with chevron button)
- **Monaco editor** in the center
- **Chat sidebar** on the right (collapsible)
- **Run controls** below the top bar (Validate, Validate & Run, Run buttons)
- **Bottom metrics drawer** for validation/run output (opens when you run commands)

## First Steps

1. **Open a workspace folder**: File → Open Folder (or Cmd+O)
   - In browser mode, you'll need to type the absolute path
   - The workspace folder should contain `.tac` files

2. **Navigate files**: Click files in the left sidebar to open them

3. **Edit and save**: Make changes, then Cmd+S to save

4. **Validate**: Click "Validate" to check for errors

5. **Run**: Click "Run" to execute the procedure

## Troubleshooting

If you still see the old UI:
- Make sure you stopped the old process completely (Ctrl+C)
- Clear your browser cache (Cmd+Shift+R for hard reload)
- Check that `tactus-ide/frontend/dist/` exists and has files
- If needed, rebuild: `cd tactus-ide/frontend && npm run build`

## Notes

- The frontend was built from the new source code
- The backend now includes workspace management, file tree, validation, and run APIs
- All keyboard shortcuts work (Cmd+O, Cmd+S, Cmd+R, etc.)
- Dark theme is enabled by default









