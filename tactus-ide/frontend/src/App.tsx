import React, { useState, useEffect, useCallback } from 'react';
import { Editor } from './Editor';
import { FileTree } from './components/FileTree';
import { ResultsSidebar } from './components/ResultsSidebar';
import { ResizeHandle } from './components/ResizeHandle';
import { Button } from './components/ui/button';
import { Separator } from './components/ui/separator';
import {
  Menubar,
  MenubarContent,
  MenubarItem,
  MenubarMenu,
  MenubarShortcut,
  MenubarTrigger,
} from './components/ui/menubar';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './components/ui/dialog';
import { Input } from './components/ui/input';
import {
  ChevronLeft,
  ChevronRight,
  Mail,
  Bell,
  Play,
  CheckCircle,
  TestTube,
  BarChart2,
} from 'lucide-react';
import { registerCommandHandler, executeCommand, ALL_COMMAND_GROUPS } from './commands/registry';
import { useEventStream } from './hooks/useEventStream';

// Detect if running in Electron (moved inside component for runtime evaluation)

interface RunResult {
  success: boolean;
  exitCode?: number;
  stdout?: string;
  stderr?: string;
  error?: string;
}

interface ValidationResult {
  valid: boolean;
  errors: Array<{
    message: string;
    line?: number;
    column?: number;
    severity: string;
  }>;
}

export const App: React.FC = () => {
  const API_BASE = import.meta.env.VITE_BACKEND_URL || '';
  const apiUrl = (path: string) => (API_BASE ? `${API_BASE}${path}` : path);
  
  // Detect if running in Electron at runtime
  const isElectron = !!(window as any).electronAPI;
  
  // Debug logging
  useEffect(() => {
    console.log('Electron detection:', {
      isElectron,
      hasElectronAPI: !!(window as any).electronAPI,
      electronAPI: (window as any).electronAPI
    });
  }, []);

  // Workspace state
  const [workspaceRoot, setWorkspaceRoot] = useState<string | null>(null);
  const [workspaceName, setWorkspaceName] = useState<string | null>(null);
  
  // File state
  const [currentFile, setCurrentFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  
  // UI state
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true);
  const [leftSidebarWidth, setLeftSidebarWidth] = useState(256); // 16rem = 256px
  const [rightSidebarWidth, setRightSidebarWidth] = useState(320); // 20rem = 320px
  
  // Dialog state
  const [openFolderDialogOpen, setOpenFolderDialogOpen] = useState(false);
  const [folderPath, setFolderPath] = useState('');
  
  // Run/validation state
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  
  // Streaming state
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const { events, isRunning: isStreaming, error: streamError } = useEventStream(streamUrl);

  // Load workspace info on mount and auto-open examples folder
  useEffect(() => {
    const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
    
    const fetchWithRetry = async (url: string, options: RequestInit = {}, maxRetries = 5) => {
      for (let i = 0; i < maxRetries; i++) {
        try {
          const response = await fetch(apiUrl(url), options);
          return response;
        } catch (err) {
          if (i === maxRetries - 1) throw err;
          // Exponential backoff: 100ms, 200ms, 400ms, 800ms, 1600ms
          const delay = 100 * Math.pow(2, i);
          console.log(`Backend not ready, retrying in ${delay}ms...`);
          await sleep(delay);
        }
      }
      throw new Error('Max retries exceeded');
    };
    
    const autoOpenExamples = async () => {
      try {
        const res = await fetchWithRetry('/api/workspace');
        const data = await res.json();
        
        if (data.root) {
          setWorkspaceRoot(data.root);
          setWorkspaceName(data.name);
        } else {
          // No workspace set, try to open examples folder
          // Try common paths where examples might be
          const possiblePaths = [
            '/Users/ryan.porter/Projects/Tactus/examples',
            './examples',
            '../examples',
            '../../examples',
            '../../../examples',
          ];
          
          for (const examplesPath of possiblePaths) {
            try {
              const setRes = await fetchWithRetry('/api/workspace', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ root: examplesPath }),
              });
              
              const setData = await setRes.json();
              if (setData.success) {
                setWorkspaceRoot(setData.root);
                setWorkspaceName(setData.name);
                console.log('Auto-opened examples folder:', setData.root);
                break;
              }
            } catch (err) {
              // Try next path
              continue;
            }
          }
        }
      } catch (err) {
        console.log('Could not auto-open examples folder:', err);
      }
    };
    
    autoOpenExamples();
  }, []);

  // Handle file selection
  const handleFileSelect = useCallback(async (path: string) => {
    try {
      const response = await fetch(apiUrl(`/api/file?path=${encodeURIComponent(path)}`));
      if (response.ok) {
        const data = await response.json();
        setCurrentFile(path);
        setFileContent(data.content);
        setHasUnsavedChanges(false);
      } else {
        console.error('Error loading file:', await response.text());
      }
    } catch (error) {
      console.error('Error loading file:', error);
    }
  }, []);

  // Handle file save
  const handleSave = useCallback(async () => {
    if (!currentFile) return;

    try {
      const response = await fetch(apiUrl('/api/file'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: currentFile,
          content: fileContent,
        }),
      });

      if (response.ok) {
        setHasUnsavedChanges(false);
      } else {
        console.error('Error saving file:', await response.text());
      }
    } catch (error) {
      console.error('Error saving file:', error);
    }
  }, [currentFile, fileContent]);

  // Handle open folder
  const handleOpenFolder = useCallback(async () => {
    if (isElectron) {
      // Use Electron native dialog
      const result = await (window as any).electronAPI.selectWorkspaceFolder();
      if (result) {
        await setWorkspace(result);
      }
    } else {
      // Show browser dialog
      setOpenFolderDialogOpen(true);
    }
  }, []);

  const setWorkspace = async (path: string) => {
    try {
      const response = await fetch(apiUrl('/api/workspace'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ root: path }),
      });

      if (response.ok) {
        const data = await response.json();
        setWorkspaceRoot(data.root);
        setWorkspaceName(data.name);
        setCurrentFile(null);
        setFileContent('');
      } else {
        console.error('Error setting workspace:', await response.text());
      }
    } catch (error) {
      console.error('Error setting workspace:', error);
    }
  };

  const handleOpenFolderSubmit = async () => {
    if (folderPath) {
      await setWorkspace(folderPath);
      setOpenFolderDialogOpen(false);
      setFolderPath('');
    }
  };

  // Validate current file
  const handleValidate = useCallback(async () => {
    if (!currentFile) {
      alert('Please select a file to validate');
      return;
    }

    // Clear old results
    setRunResult(null);
    setValidationResult(null);

    try {
      // First, save the file content
      await fetch(apiUrl('/api/file'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: currentFile,
          content: fileContent,
        }),
      });

      // Then start streaming validation results
      const url = apiUrl(`/api/validate/stream?path=${encodeURIComponent(currentFile)}`);
      setStreamUrl(url);
    } catch (error) {
      console.error('Error validating:', error);
    }
  }, [currentFile, fileContent]);

  // Run current file with streaming
  const handleRun = useCallback(async () => {
    if (!currentFile) {
      alert('Please select a file to run');
      return;
    }

    // Clear old results
    setRunResult(null);
    setValidationResult(null);
    
    try {
      // First, save the file content
      await fetch(apiUrl('/api/file'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: currentFile,
          content: fileContent,
        }),
      });
      
      // Then start streaming (GET request, no content in URL)
      const url = apiUrl(`/api/run/stream?path=${encodeURIComponent(currentFile)}`);
      setStreamUrl(url);
    } catch (error) {
      console.error('Error saving file before run:', error);
    }
  }, [currentFile, fileContent]);

  // Test current file
  const handleTest = useCallback(async () => {
    if (!currentFile) {
      alert('Please select a file to test');
      return;
    }

    // Clear old results
    setRunResult(null);
    setValidationResult(null);
    
    try {
      // First, save the file content
      await fetch(apiUrl('/api/file'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: currentFile,
          content: fileContent,
        }),
      });
      
      // Then start streaming test results (mock mode by default)
      const url = apiUrl(`/api/test/stream?path=${encodeURIComponent(currentFile)}&mock=true`);
      setStreamUrl(url);
    } catch (error) {
      console.error('Error running tests:', error);
    }
  }, [currentFile, fileContent]);

  // Evaluate current file
  const handleEvaluate = useCallback(async () => {
    if (!currentFile) {
      alert('Please select a file to evaluate');
      return;
    }

    // Clear old results
    setRunResult(null);
    setValidationResult(null);
    
    try {
      // First, save the file content
      await fetch(apiUrl('/api/file'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: currentFile,
          content: fileContent,
        }),
      });
      
      // Then start streaming evaluation results (mock mode by default, 10 runs)
      const url = apiUrl(`/api/evaluate/stream?path=${encodeURIComponent(currentFile)}&mock=true&runs=10`);
      setStreamUrl(url);
    } catch (error) {
      console.error('Error running evaluation:', error);
    }
  }, [currentFile, fileContent]);

  // Register command handlers
  useEffect(() => {
    registerCommandHandler('file.openFolder', handleOpenFolder);
    registerCommandHandler('file.save', handleSave);
    registerCommandHandler('view.toggleLeftSidebar', () => setLeftSidebarOpen((v) => !v));
    registerCommandHandler('view.toggleRightSidebar', () => setRightSidebarOpen((v) => !v));
    registerCommandHandler('run.validate', handleValidate);
    registerCommandHandler('run.run', handleRun);
    registerCommandHandler('run.test', handleTest);
    registerCommandHandler('run.evaluate', handleEvaluate);
  }, [handleOpenFolder, handleSave, handleValidate, handleRun, handleTest, handleEvaluate]);

  // Listen for Electron commands
  useEffect(() => {
    if (isElectron) {
      (window as any).electronAPI.onCommand((cmdId: string) => {
        executeCommand(cmdId);
      });
    }
  }, []);

  // Keyboard shortcut for toggling sidebar (Ctrl+B / Cmd+B)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const modKey = isMac ? e.metaKey : e.ctrlKey;
      
      if (modKey && e.key === 'b') {
        e.preventDefault();
        setLeftSidebarOpen(v => !v);
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="flex flex-col h-screen bg-background text-foreground dark">
      {/* Top bar - only show in browser mode */}
      {!isElectron && (
        <div className="flex items-center justify-between h-12 px-4 border-b bg-card">
          <div className="flex items-center gap-4">
            <span className="font-semibold">Tactus</span>
            <Separator orientation="vertical" className="h-6" />
            <Menubar className="border-0 bg-transparent shadow-none">
              {ALL_COMMAND_GROUPS.map((group) => (
                <MenubarMenu key={group.label}>
                  <MenubarTrigger>{group.label}</MenubarTrigger>
                  <MenubarContent>
                    {group.commands.map((cmd) => (
                      <MenubarItem key={cmd.id} onClick={() => executeCommand(cmd.id)}>
                        {cmd.label}
                        {cmd.shortcut && <MenubarShortcut>{cmd.shortcut}</MenubarShortcut>}
                      </MenubarItem>
                    ))}
                  </MenubarContent>
                </MenubarMenu>
              ))}
            </Menubar>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {workspaceName || 'No folder open'}
              {currentFile && ` • ${currentFile}`}
              {hasUnsavedChanges && ' •'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon">
              <Mail className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon">
              <Bell className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar */}
        {leftSidebarOpen && (
          <>
            <div className="bg-card flex flex-col" style={{ width: `${leftSidebarWidth}px` }}>
              <FileTree
                workspaceRoot={workspaceRoot}
                workspaceName={workspaceName}
                onFileSelect={handleFileSelect}
                selectedFile={currentFile}
              />
            </div>
            <ResizeHandle
              direction="left"
              onResize={(delta) => {
                setLeftSidebarWidth((prev) => Math.max(200, Math.min(600, prev + delta)));
              }}
            />
          </>
        )}

        {/* Editor area */}
        <div className="flex-1 min-w-0 flex flex-col">
          {/* Run controls - only over editor */}
          {currentFile && (
            <div className="flex items-center gap-1 px-2 py-1 border-b bg-muted/30">
              <Button size="sm" variant="ghost" onClick={handleValidate} className="h-7 text-xs">
                <CheckCircle className="h-3 w-3 mr-1" />
                Validate
              </Button>
              <Button size="sm" variant="ghost" onClick={handleTest} className="h-7 text-xs">
                <TestTube className="h-3 w-3 mr-1" />
                Test
              </Button>
              <Button size="sm" variant="ghost" onClick={handleRun} disabled={isRunning} className="h-7 text-xs">
                <Play className="h-3 w-3 mr-1" />
                {isRunning ? 'Running...' : 'Run'}
              </Button>
              <Button size="sm" variant="ghost" onClick={handleEvaluate} className="h-7 text-xs">
                <BarChart2 className="h-3 w-3 mr-1" />
                Evaluate
              </Button>
              {runResult && (
                <span className={`text-xs ml-2 ${runResult.success ? 'text-green-600' : 'text-red-600'}`}>
                  {runResult.success ? '✓ Success' : '✗ Failed'}
                </span>
              )}
            </div>
          )}
          <div className="flex-1 min-h-0">
            <Editor
              initialValue={fileContent}
              onValueChange={(value) => {
                setFileContent(value);
                setHasUnsavedChanges(true);
              }}
              filePath={currentFile || undefined}
            />
          </div>
        </div>

        {/* Right sidebar */}
        {rightSidebarOpen && (
          <>
            <ResizeHandle
              direction="right"
              onResize={(delta) => {
                setRightSidebarWidth((prev) => Math.max(200, Math.min(800, prev + delta)));
              }}
            />
            <div className="bg-card flex flex-col" style={{ width: `${rightSidebarWidth}px` }}>
              <ResultsSidebar 
                events={events} 
                isRunning={isStreaming} 
                onClear={() => setStreamUrl(null)} 
              />
            </div>
          </>
        )}
      </div>

      {/* Open Folder Dialog (browser mode) */}
      <Dialog open={openFolderDialogOpen} onOpenChange={setOpenFolderDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Open Folder</DialogTitle>
            <DialogDescription>
              Enter the absolute path to the folder you want to open.
            </DialogDescription>
          </DialogHeader>
          <Input
            placeholder="/path/to/your/project"
            value={folderPath}
            onChange={(e) => setFolderPath(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleOpenFolderSubmit();
              }
            }}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpenFolderDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleOpenFolderSubmit}>Open</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};




