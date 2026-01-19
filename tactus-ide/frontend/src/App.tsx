import React, { useState, useEffect, useCallback, useRef } from 'react';
import { nanoid } from 'nanoid';
import { Editor, EditorHandle } from './Editor';
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './components/ui/dropdown-menu';
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
import { registerCommandHandler, executeCommand, ALL_COMMAND_GROUPS, RUN_COMMANDS } from './commands/registry';
import { useEventStream } from './hooks/useEventStream';
import { ThemeProvider } from './components/theme-provider';
import { ResultsHistoryState, RunHistory } from './types/results';
import { ProcedureMetadata } from './types/metadata';
import { AnyEvent, TestCompletedEvent } from './types/events';
import { ProcedureInputsModal } from './components/ProcedureInputsModal';
import { TestOptionsModal, TestOptions } from './components/TestOptionsModal';
import { AboutDialog } from './components/AboutDialog';
import { PreferencesView } from './components/PreferencesView';
import { AuthErrorDialog } from './components/AuthErrorDialog';

// Detect if running in Electron (moved inside component for runtime evaluation)

// Extract scenario names from Gherkin specifications data
function extractScenarioNames(specifications: { text: string } | null | undefined): string[] {
  if (!specifications?.text) return [];

  const scenarios: string[] = [];
  const lines = specifications.text.split('\n');

  for (const line of lines) {
    const trimmed = line.trim();
    // Match "Scenario: Name" or "Scenario Outline: Name"
    const match = trimmed.match(/^Scenario(?:\s+Outline)?:\s*(.+)$/);
    if (match) {
      scenarios.push(match[1].trim());
    }
  }

  return scenarios;
}

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

  // Check if this is a preferences-only window (for Electron)
  const urlParams = new URLSearchParams(window.location.search);
  const isPreferencesOnly = urlParams.get('preferencesOnly') === 'true';

  // Debug logging
  useEffect(() => {
    console.log('Electron detection:', {
      isElectron,
      hasElectronAPI: !!(window as any).electronAPI,
      electronAPI: (window as any).electronAPI,
      isPreferencesOnly
    });
  }, [isPreferencesOnly]);

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
  const [showPreferences, setShowPreferences] = useState(false);

  // Run/validation state
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  
  // Streaming state
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const { events, isRunning: isStreaming, error: streamError } = useEventStream(streamUrl);

  // Auth error dialog state
  const [authErrorDialogOpen, setAuthErrorDialogOpen] = useState(false);
  const [authErrorMessage, setAuthErrorMessage] = useState<string>('');

  // Results history and metadata state
  const [resultsHistory, setResultsHistory] = useState<ResultsHistoryState>({});
  const [activeTab, setActiveTab] = useState<'procedure' | 'results' | 'chat'>('procedure');
  const [procedureMetadata, setProcedureMetadata] = useState<ProcedureMetadata | null>(null);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);

  // Container status state
  const [containerStatus, setContainerStatus] = useState<{
    status: 'idle' | 'starting' | 'ready' | 'disabled' | 'error';
    spinupMs?: number;
  }>({ status: 'idle' });

  // Input modal state
  const [inputModalOpen, setInputModalOpen] = useState(false);
  const [pendingInputs, setPendingInputs] = useState<Record<string, any> | null>(null);
  const [testOptionsModalOpen, setTestOptionsModalOpen] = useState(false);
  const [aboutDialogOpen, setAboutDialogOpen] = useState(false);

  // Editor ref for programmatic navigation
  const editorRef = useRef<EditorHandle>(null);

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
          // Try common relative paths where examples might be
          const possiblePaths = [
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
  const handleFileSelect = useCallback(async (path: string, switchTab: boolean = true) => {
    try {
      const response = await fetch(apiUrl(`/api/file?path=${encodeURIComponent(path)}`));
      if (response.ok) {
        const data = await response.json();
        setCurrentFile(path);
        setFileContent(data.content);
        setHasUnsavedChanges(false);

        // Only switch to Procedure tab if requested (default true for backward compatibility)
        if (switchTab) {
          setActiveTab('procedure');
        }

        // Fetch metadata
        fetchProcedureMetadata(path);
      } else {
        console.error('Error loading file:', await response.text());
      }
    } catch (error) {
      console.error('Error loading file:', error);
    }
  }, [fetchProcedureMetadata]);

  // Handle jumping to source from checkpoint
  const handleJumpToSource = useCallback(async (filePath: string, lineNumber: number) => {
    console.log('Jump to source called:', { filePath, lineNumber });

    // First open the file (but don't switch tabs)
    await handleFileSelect(filePath, false);
    console.log('File opened, waiting to reveal line...');

    // Then reveal the line in the editor (with a small delay to ensure editor has rendered)
    setTimeout(() => {
      console.log('Attempting to reveal line, editorRef.current:', !!editorRef.current);
      if (editorRef.current) {
        editorRef.current.revealLine(lineNumber);
        console.log('Line revealed successfully');
      } else {
        console.error('Editor ref is null!');
      }
    }, 100);
  }, [handleFileSelect]);

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
  const createNewRun = useCallback((
    operationType: 'validate' | 'test' | 'evaluate' | 'run',
    inputs?: Record<string, any>
  ) => {
    if (!currentFile) return null;

    const runId = nanoid();
    setCurrentRunId(runId);

    setResultsHistory((prev) => {
      const fileHistory = prev[currentFile] || { filePath: currentFile, runs: [] };

      // Collapse all previous runs
      const updatedRuns = fileHistory.runs.map((run) => ({ ...run, isExpanded: false }));

      // Add new run at the END (bottom of list) since newest should be last
      const newRun: RunHistory = {
        id: runId,
        timestamp: new Date().toISOString(),
        operationType,
        events: [],
        isExpanded: true,
        status: 'running',
        inputs, // Include inputs in initial creation
      };

      // Add new run at the bottom, keep existing persisted runs
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

  // Execute run with inputs (called after modal submission or directly if no inputs)
  const executeRunWithInputs = useCallback(async (inputs: Record<string, any>) => {
    if (!currentFile) return;

    // Clear stream first to reset events
    setStreamUrl(null);

    // Create new run entry with inputs (passed directly to avoid race condition)
    const runId = createNewRun('run', inputs);

    // Clear old results
    setRunResult(null);
    setValidationResult(null);

    try {
      // Use POST request with inputs in body for SSE streaming
      // The useEventStream hook will detect this is a POST config and use fetch streaming
      const url = apiUrl('/api/run/stream');
      const requestBody = {
        path: currentFile,
        content: fileContent,
        inputs: inputs,
        _runId: runId, // Add unique runId to force URL change for each run
      };

      // Pass POST config as JSON string to useEventStream
      setStreamUrl(JSON.stringify({ url, method: 'POST', body: requestBody }));
    } catch (error) {
      console.error('Error preparing run request:', error);
    }
  }, [currentFile, fileContent, createNewRun]);

  // Handle HITL response submission
  const handleHITLRespond = useCallback(async (requestId: string, value: any) => {
    try {
      const url = apiUrl(`/api/hitl/response/${requestId}`);
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      console.log(`HITL response sent for ${requestId}:`, value);
    } catch (error) {
      console.error('Error sending HITL response:', error);
      alert('Failed to send response. Please try again.');
    }
  }, []);

  // Run current file with streaming
  const handleRun = useCallback(async () => {
    if (!currentFile) {
      alert('Please select a file to run');
      return;
    }

    // Check if procedure has input parameters
    const hasInputs = Object.keys(procedureMetadata?.input ?? {}).length > 0;

    if (hasInputs) {
      // Show modal to collect inputs
      setInputModalOpen(true);
      return;
    }

    // No inputs needed, run directly
    executeRunWithInputs({});
  }, [currentFile, procedureMetadata, executeRunWithInputs]);

  // Test current file - opens options modal
  const handleTest = useCallback(() => {
    if (!currentFile) {
      alert('Please select a file to test');
      return;
    }

    if (!procedureMetadata?.specifications) {
      alert('No specifications found in this file');
      return;
    }

    setTestOptionsModalOpen(true);
  }, [currentFile, procedureMetadata]);

  // Run tests with specified options
  const handleTestWithOptions = useCallback(async (options: TestOptions) => {
    if (!currentFile) return;

    setTestOptionsModalOpen(false);

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

      // Build URL with options
      let url = apiUrl(`/api/test/stream?path=${encodeURIComponent(currentFile)}&mock=${options.mockEnabled}`);
      if (options.scenario) {
        url += `&scenario=${encodeURIComponent(options.scenario)}`;
      }
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
    registerCommandHandler('tactus.preferences', () => setShowPreferences(true));
    registerCommandHandler('tactus.about', () => setAboutDialogOpen(true));
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

  // Function to detect authentication errors
  const isAuthenticationError = useCallback((errorMessage: string, errorType?: string): boolean => {
    if (!errorMessage) return false;

    const lowercaseError = errorMessage.toLowerCase();
    const lowercaseType = (errorType || '').toLowerCase();

    return (
      lowercaseError.includes('api authentication failed') ||
      lowercaseError.includes('missing or invalid api key') ||
      lowercaseError.includes('authenticationerror') ||
      lowercaseError.includes('unauthorized') ||
      lowercaseType.includes('authenticationerror') ||
      lowercaseType.includes('tactusruntimeerror')
    );
  }, []);

  // Function to open settings (handles both Electron and web)
  const handleOpenSettings = useCallback(() => {
    if (isElectron) {
      // In Electron, use the electronAPI to open settings window
      if ((window as any).electronAPI?.openPreferences) {
        (window as any).electronAPI.openPreferences();
      }
    } else {
      // In web app, show inline preferences
      setShowPreferences(true);
    }
  }, [isElectron]);

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

  // Load persistent runs from storage when file changes
  useEffect(() => {
    if (!currentFile) return;

    const loadPersistedRuns = async () => {
      try {
        // Extract procedure name from file path
        const fileName = currentFile.split('/').pop();
        if (!fileName || !fileName.endsWith('.tac')) return;

        const procedureName = 'ide-' + fileName.replace('.tac', '');

        // Fetch runs from trace API
        const response = await fetch(apiUrl(`/api/traces/runs?procedure=${encodeURIComponent(procedureName)}&limit=50`));
        if (!response.ok) return;

        const data = await response.json();
        const runs = data.runs || [];

        if (runs.length === 0) return;

        // Load events for each run in parallel
        const runsWithEvents = await Promise.all(
          runs.map(async (run: any) => {
            try {
              // Try to load events for this run
              const eventsResponse = await fetch(apiUrl(`/api/traces/runs/${run.run_id}/events`));
              const events = eventsResponse.ok ? (await eventsResponse.json()).events || [] : [];

              return {
                id: run.run_id,
                timestamp: run.start_time,
                operationType: 'run' as const,
                events: events,
                isExpanded: false,
                status: run.status === 'COMPLETED' ? 'success' as const
                      : run.status === 'FAILED' ? 'failed' as const
                      : run.status === 'RUNNING' ? 'running' as const
                      : 'error' as const,
              };
            } catch (err) {
              // If events can't be loaded, return run without events
              return {
                id: run.run_id,
                timestamp: run.start_time,
                operationType: 'run' as const,
                events: [],
                isExpanded: false,
                status: run.status === 'COMPLETED' ? 'success' as const
                      : run.status === 'FAILED' ? 'failed' as const
                      : run.status === 'RUNNING' ? 'running' as const
                      : 'error' as const,
              };
            }
          })
        );

        // Update results history with persisted runs
        setResultsHistory((prev) => ({
          ...prev,
          [currentFile]: {
            filePath: currentFile,
            runs: runsWithEvents,
          },
        }));
      } catch (error) {
        console.error('Failed to load persisted runs:', error);
      }
    };

    loadPersistedRuns();
  }, [currentFile]);

  // Track container status from streaming events
  useEffect(() => {
    // Reset container status when events are cleared (new execution starting)
    if (events.length === 0 && isStreaming) {
      setContainerStatus({ status: 'idle' });
      return;
    }

    if (events.length > 0) {
      const lastEvent = events[events.length - 1];
      if (lastEvent.event_type === 'container_status') {
        const statusEvent = lastEvent as import('./types/events').ContainerStatusEvent;
        if (statusEvent.status === 'ready') {
          setContainerStatus({
            status: 'ready',
            spinupMs: statusEvent.spinup_duration_ms,
          });
        } else if (statusEvent.status === 'starting') {
          setContainerStatus({ status: 'starting' });
        } else if (statusEvent.status === 'stopped') {
          // Don't reset to idle - keep the 'ready' status visible to show spinup time
          // Container status will be reset when a new execution starts
        } else if (statusEvent.status === 'disabled') {
          setContainerStatus({ status: 'disabled' });
        } else if (statusEvent.status === 'error') {
          setContainerStatus({ status: 'error' });
        }
      }
    }

    // Don't reset container status when streaming stops - we want to show spinup time
    // Container status persists after execution completes to show spinup duration
  }, [events, isStreaming]);

  // Sync streaming events into current run
  useEffect(() => {
    if (currentFile && currentRunId && events.length > 0) {
      setResultsHistory((prev) => {
        const fileHistory = prev[currentFile];
        if (!fileHistory || fileHistory.runs.length === 0) return prev;

        const currentRun = fileHistory.runs.find((run) => run.id === currentRunId);
        if (!currentRun) return prev;

        // Extract run_id from completion event if available
        let backendRunId = currentRunId;
        const lastEvent = events[events.length - 1];
        if (lastEvent?.event_type === 'execution' && lastEvent.details?.run_id) {
          backendRunId = lastEvent.details.run_id;
        }

        // Determine status from events
        let status: RunHistory['status'] = 'running';
        if (!isStreaming) {
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

        // Update current run with new events, status, and backend run ID
        const updatedRuns = fileHistory.runs.map((run) =>
          run.id === currentRunId
            ? { ...run, id: backendRunId, events: [...events], status }
            : run
        );

        // Update currentRunId if it changed
        if (backendRunId !== currentRunId && !isStreaming) {
          setCurrentRunId(backendRunId);
        }

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

  // Detect authentication errors in execution events
  useEffect(() => {
    if (!events || events.length === 0) return;

    // Check the most recent events for authentication errors
    const recentEvents = events.slice(-5); // Check last 5 events

    for (const event of recentEvents) {
      if (event.event_type === 'execution' && event.lifecycle_stage === 'error') {
        const errorMsg = event.details?.error || '';
        const errorType = event.details?.error_type || '';

        if (isAuthenticationError(errorMsg, errorType)) {
          setAuthErrorMessage(errorMsg);
          setAuthErrorDialogOpen(true);
          break;
        }
      }

      if (event.event_type === 'execution_summary' && event.error_message) {
        const errorMsg = event.error_message || '';
        const errorType = event.error_type || '';

        if (isAuthenticationError(errorMsg, errorType)) {
          setAuthErrorMessage(errorMsg);
          setAuthErrorDialogOpen(true);
          break;
        }
      }
    }
  }, [events, isAuthenticationError]);

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

  // If this is a preferences-only window, render only the preferences UI
  if (isPreferencesOnly) {
    return (
      <div className="flex items-center justify-center h-screen bg-background text-foreground p-4">
        <PreferencesView
          onClose={() => window.close()}
          onSave={() => {
            // Config saved successfully - could close window or show message
            console.log('Preferences saved');
          }}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-background text-foreground">
      {/* Top bar - only show in browser mode */}
      {!isElectron && (
        <div className="flex items-center justify-between h-12 px-4 border-b bg-card">
          <div className="flex items-center gap-4">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="focus:outline-none">
                  <Logo className="text-xl font-semibold cursor-pointer hover:opacity-80 transition-opacity" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem onClick={() => executeCommand('tactus.preferences')}>
                  Settings...
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => executeCommand('tactus.about')}>
                  About Tactus
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Menubar className="border-0 bg-transparent shadow-none">
              {ALL_COMMAND_GROUPS.map((group) => {
                // Only show Procedure menu for .tac files
                if (group.label === RUN_COMMANDS.label && !currentFile?.endsWith('.tac')) {
                  return null;
                }

                return (
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
                );
              })}
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
                  ref={editorRef}
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
                containerStatus={containerStatus}
                onToggleRunExpansion={handleToggleRunExpansion}
                onJumpToSource={handleJumpToSource}
                onHITLRespond={handleHITLRespond}
                workspaceRoot={workspaceRoot}
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

      {/* Procedure Inputs Modal */}
      {procedureMetadata?.input && (
        <ProcedureInputsModal
          open={inputModalOpen}
          onOpenChange={setInputModalOpen}
          parameters={procedureMetadata.input}
          onSubmit={(values) => {
            setInputModalOpen(false);
            executeRunWithInputs(values);
          }}
          onCancel={() => setInputModalOpen(false)}
        />
      )}

      {/* Test Options Modal */}
      <TestOptionsModal
        open={testOptionsModalOpen}
        onOpenChange={setTestOptionsModalOpen}
        scenarios={extractScenarioNames(procedureMetadata?.specifications)}
        onSubmit={handleTestWithOptions}
        onCancel={() => setTestOptionsModalOpen(false)}
      />

      {/* About Dialog */}
      <AboutDialog
        open={aboutDialogOpen}
        onOpenChange={setAboutDialogOpen}
      />

      {/* Auth Error Dialog */}
      <AuthErrorDialog
        open={authErrorDialogOpen}
        onOpenChange={setAuthErrorDialogOpen}
        errorMessage={authErrorMessage}
        onOpenSettings={handleOpenSettings}
      />

      {/* Preferences View */}
      {showPreferences && (
        <PreferencesView
          onClose={() => setShowPreferences(false)}
          onSave={() => {
            // Config saved successfully
            setShowPreferences(false);
          }}
        />
      )}
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


