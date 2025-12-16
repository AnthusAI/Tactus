import React, { useState, useEffect, useCallback } from 'react';
import { nanoid } from 'nanoid';
import { Editor } from './Editor';
import { FileTree } from './components/FileTree';
import { ResultsSidebar } from './components/ResultsSidebar';
import { ResizeHandle } from './components/ResizeHandle';
import { Button } from './components/ui/button';
import { Logo } from './components/ui/logo';
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
import { ThemeProvider } from './components/theme-provider';
import { ResultsHistoryState, RunHistory } from './types/results';
import { ProcedureMetadata } from './types/metadata';
import { AnyEvent, TestCompletedEvent } from './types/events';

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

const AppContent: React.FC = () => {
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

  // Results history and metadata state
  const [resultsHistory, setResultsHistory] = useState<ResultsHistoryState>({});
  const [activeTab, setActiveTab] = useState<'procedure' | 'results'>('procedure');
  const [procedureMetadata, setProcedureMetadata] = useState<ProcedureMetadata | null>(null);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);

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

  // Fetch procedure metadata
  const fetchProcedureMetadata = useCallback(async (filePath: string) => {
    setMetadataLoading(true);
    try {
      const response = await fetch(
        apiUrl(`/api/procedure/metadata?path=${encodeURIComponent(filePath)}`)
      );
      const data = await response.json();
      if (data.success) {
        setProcedureMetadata(data.metadata);
      } else {
        setProcedureMetadata(null);
        console.error('Failed to load metadata:', data.error);
      }
    } catch (error) {
      console.error('Error fetching metadata:', error);
      setProcedureMetadata(null);
    } finally {
      setMetadataLoading(false);
    }
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

        // Switch to Procedure tab
        setActiveTab('procedure');

        // Fetch metadata
        fetchProcedureMetadata(path);
      } else {
        console.error('Error loading file:', await response.text());
      }
    } catch (error) {
      console.error('Error loading file:', error);
    }
  }, [fetchProcedureMetadata]);

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

  // Helper function to create a new run entry
  const createNewRun = useCallback((operationType: 'validate' | 'test' | 'evaluate' | 'run') => {
    if (!currentFile) return null;

    const runId = nanoid();
    setCurrentRunId(runId);

    setResultsHistory((prev) => {
      const fileHistory = prev[currentFile] || { filePath: currentFile, runs: [] };

      // Collapse all previous runs
      const updatedRuns = fileHistory.runs.map((run) => ({ ...run, isExpanded: false }));

      // Add new run at the END (bottom of list)
      const newRun: RunHistory = {
        id: runId,
        timestamp: new Date().toISOString(),
        operationType,
        events: [],
        isExpanded: true,
        status: 'running',
      };

      // Keep all runs (no limit)
      const allRuns = [...updatedRuns, newRun];
      return {
        ...prev,
        [currentFile]: {
          ...fileHistory,
          runs: allRuns,
        },
      };
    });

    // Switch to Results tab
    setActiveTab('results');

    return runId;
  }, [currentFile]);

  // Validate current file
  const handleValidate = useCallback(async () => {
    if (!currentFile) {
      alert('Please select a file to validate');
      return;
    }

    // Clear stream first to reset events
    setStreamUrl(null);

    // Create new run entry
    createNewRun('validate');

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
  }, [currentFile, fileContent, createNewRun]);

  // Run current file with streaming
  const handleRun = useCallback(async () => {
    if (!currentFile) {
      alert('Please select a file to run');
      return;
    }

    // Clear stream first to reset events
    setStreamUrl(null);

    // Create new run entry
    createNewRun('run');

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
  }, [currentFile, fileContent, createNewRun]);

  // Test current file
  const handleTest = useCallback(async () => {
    if (!currentFile) {
      alert('Please select a file to test');
      return;
    }

    // Clear stream first to reset events
    setStreamUrl(null);

    // Create new run entry
    createNewRun('test');

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

      // Then start streaming test results (real mode by default - uses actual LLM)
      const url = apiUrl(`/api/test/stream?path=${encodeURIComponent(currentFile)}&mock=false`);
      setStreamUrl(url);
    } catch (error) {
      console.error('Error running tests:', error);
    }
  }, [currentFile, fileContent, createNewRun]);

  // Evaluate current file (Pydantic Evals)
  const handleEvaluate = useCallback(async () => {
    console.log('[Evaluate] Button clicked', { currentFile, hasContent: !!fileContent });

    if (!currentFile) {
      alert('Please select a file to evaluate');
      return;
    }

    // Clear stream first to reset events
    setStreamUrl(null);

    // Create new run entry
    createNewRun('evaluate');

    // Clear old results
    setRunResult(null);
    setValidationResult(null);

    try {
      console.log('[Evaluate] Saving file content...');
      // First, save the file content
      await fetch(apiUrl('/api/file'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: currentFile,
          content: fileContent,
        }),
      });

      // Then start streaming Pydantic Eval results
      const url = apiUrl(`/api/pydantic-eval/stream?path=${encodeURIComponent(currentFile)}&runs=1`);
      console.log('[Evaluate] Starting stream:', url);
      setStreamUrl(url);
    } catch (error) {
      console.error('[Evaluate] Error running Pydantic Evals:', error);
    }
  }, [currentFile, fileContent, createNewRun]);


  // Register command handlers
  useEffect(() => {
    registerCommandHandler('file.openFolder', handleOpenFolder);
    registerCommandHandler('file.save', handleSave);
    registerCommandHandler('view.toggleLeftSidebar', () => setLeftSidebarOpen((v) => !v));
    registerCommandHandler('view.toggleRightSidebar', () => setRightSidebarOpen((v) => !v));
    registerCommandHandler('run.validate', handleValidate);
    registerCommandHandler('run.run', handleRun);
    registerCommandHandler('run.test', handleTest);
    registerCommandHandler('run.evaluate', handleEvaluate);  // Pydantic Evals
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

  // Sync streaming events into current run
  useEffect(() => {
    if (currentFile && currentRunId && events.length > 0) {
      setResultsHistory((prev) => {
        const fileHistory = prev[currentFile];
        if (!fileHistory || fileHistory.runs.length === 0) return prev;

        const currentRun = fileHistory.runs.find((run) => run.id === currentRunId);
        if (!currentRun) return prev;

        // Determine status from events
        let status: RunHistory['status'] = 'running';
        if (!isStreaming) {
          const lastEvent = events[events.length - 1];
          if (lastEvent?.event_type === 'execution') {
            if (lastEvent.lifecycle_stage === 'error') status = 'error';
            else if (lastEvent.lifecycle_stage === 'complete') status = 'success';
          } else if (lastEvent?.event_type === 'test_completed') {
            status = (lastEvent as TestCompletedEvent).result.failed_scenarios > 0 ? 'failed' : 'success';
          } else if (lastEvent?.event_type === 'evaluation_completed') {
            status = 'success';
          } else {
            status = 'success';
          }
        }

        // Update current run with new events and status
        const updatedRuns = fileHistory.runs.map((run) =>
          run.id === currentRunId
            ? { ...run, events: [...events], status }
            : run
        );

        return {
          ...prev,
          [currentFile]: {
            ...fileHistory,
            runs: updatedRuns,
          },
        };
      });
    }
  }, [events, isStreaming, currentFile, currentRunId]);

  // Handler to toggle run expansion
  const handleToggleRunExpansion = useCallback((runId: string) => {
    if (!currentFile) return;

    setResultsHistory((prev) => {
      const fileHistory = prev[currentFile];
      if (!fileHistory) return prev;

      const updatedRuns = fileHistory.runs.map((run) =>
        run.id === runId ? { ...run, isExpanded: !run.isExpanded } : run
      );

      return {
        ...prev,
        [currentFile]: {
          ...fileHistory,
          runs: updatedRuns,
        },
      };
    });
  }, [currentFile]);

  return (
    <div className="flex flex-col h-screen bg-background text-foreground dark">
      {/* Top bar - only show in browser mode */}
      {!isElectron && (
        <div className="flex items-center justify-between h-12 px-4 border-b bg-card">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-[0.1em]">
              <span className="font-semibold font-jersey text-xl tracking-wider">Tactus</span>
              <Logo className="h-[1rem] w-auto -translate-y-[0.135rem] scale-110" />
            </div>
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
          {currentFile ? (
            <>
              {/* Run controls - only show for .tac files */}
              {currentFile.endsWith('.tac') && (
                <div className="flex items-center gap-1 px-2 border-b bg-muted/30 h-10">
                  <Button size="sm" variant="ghost" onClick={handleValidate} className="h-8 text-sm">
                    <CheckCircle className="h-4 w-4 mr-1.5" />
                    Validate
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={handleTest}
                    disabled={!procedureMetadata?.specifications}
                    className="h-8 text-sm"
                  >
                    <TestTube className="h-4 w-4 mr-1.5" />
                    Test
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={handleEvaluate}
                    disabled={!procedureMetadata?.evaluations}
                    className="h-8 text-sm"
                  >
                    <BarChart2 className="h-4 w-4 mr-1.5" />
                    Evaluate
                  </Button>
                  <Button size="sm" variant="ghost" onClick={handleRun} disabled={isRunning} className="h-8 text-sm">
                    <Play className="h-4 w-4 mr-1.5" />
                    {isRunning ? 'Running...' : 'Run'}
                  </Button>
                  {runResult && (
                    <span className={`text-sm ml-2 ${runResult.success ? 'text-green-600' : 'text-red-600'}`}>
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
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <p className="text-lg mb-2">No file open</p>
                <p className="text-sm">Select a file from the sidebar to begin</p>
              </div>
            </div>
          )}
        </div>

        {/* Right sidebar - only show for .tac files */}
        {rightSidebarOpen && currentFile?.endsWith('.tac') && (
          <>
            <ResizeHandle
              direction="right"
              onResize={(delta) => {
                setRightSidebarWidth((prev) => Math.max(200, Math.min(800, prev + delta)));
              }}
            />
            <div className="bg-card flex flex-col" style={{ width: `${rightSidebarWidth}px` }}>
              <ResultsSidebar
                currentFile={currentFile}
                activeTab={activeTab}
                onTabChange={setActiveTab}
                procedureMetadata={procedureMetadata}
                metadataLoading={metadataLoading}
                resultsHistory={currentFile ? resultsHistory[currentFile] : null}
                isRunning={isStreaming}
                onToggleRunExpansion={handleToggleRunExpansion}
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

export const App: React.FC = () => {
  return (
    <ThemeProvider defaultTheme="system" storageKey="tactus-ui-theme">
      <AppContent />
    </ThemeProvider>
  );
};


