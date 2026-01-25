import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Loader2, Monitor, AlertTriangle, MessageSquare } from 'lucide-react';
import { FileResultsHistory, RunHistory } from '@/types/results';
import { ProcedureMetadata } from '@/types/metadata';
import { CheckpointEntry } from '@/types/tracing';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ProcedureTab } from './ProcedureTab';
import { CollapsibleRun } from './CollapsibleRun';
import { ChatSidebar } from './ChatSidebar';
import { serializeRunToYaml } from '@/utils/runExport';
import { copyTextToClipboard } from '@/utils/clipboard';

interface ResultsSidebarProps {
  currentFile: string | null;
  activeTab: 'procedure' | 'results' | 'chat';
  onTabChange: (tab: 'procedure' | 'results' | 'chat') => void;

  // Procedure tab
  procedureMetadata: ProcedureMetadata | null;
  metadataLoading: boolean;

  // Results tab
  resultsHistory: FileResultsHistory | null;
  isRunning: boolean;
  onToggleRunExpansion: (runId: string) => void;
  onJumpToSource?: (filePath: string, lineNumber: number) => void;
  onHITLRespond?: (requestId: string, value: any) => void;
  containerStatus: {
    status: 'idle' | 'starting' | 'ready' | 'disabled' | 'error';
    spinupMs?: number;
  };

  // Chat tab
  workspaceRoot: string | null;
}

export const ResultsSidebar: React.FC<ResultsSidebarProps> = ({
  currentFile,
  activeTab,
  onTabChange,
  procedureMetadata,
  metadataLoading,
  resultsHistory,
  isRunning,
  onToggleRunExpansion,
  onJumpToSource,
  onHITLRespond,
  containerStatus,
  workspaceRoot,
}) => {
  const resultsContentRef = useRef<HTMLDivElement>(null);
  const lastRunCountRef = useRef<number>(0);
  const shouldAutoScrollRef = useRef<boolean>(true);

  // Extract procedure name from current file path
  // The backend saves runs with "ide-{filename}" as the procedure_name
  const procedureName = currentFile
    ? `ide-${currentFile.split('/').pop()?.replace('.tac', '')}` || undefined
    : undefined;

  // Fetch and cache checkpoint data for runs
  const [checkpointCache, setCheckpointCache] = useState<Map<string, CheckpointEntry[]>>(new Map());
  const [fetchingRuns, setFetchingRuns] = useState<Set<string>>(new Set());
  const [failedRuns, setFailedRuns] = useState<Set<string>>(new Set());

  // Clear caches when file changes
  useEffect(() => {
    setCheckpointCache(new Map());
    setFetchingRuns(new Set());
    setFailedRuns(new Set());
  }, [currentFile]);

  // Fetch checkpoints for a specific run when needed
  const fetchCheckpointsForRun = useCallback(async (runId: string) => {
    // Skip if already failed
    if (failedRuns.has(runId)) {
      return [];
    }

    try {
      const url = `${import.meta.env.VITE_BACKEND_URL || ''}/api/traces/runs/${runId}/checkpoints?procedure=${encodeURIComponent(procedureName || '')}`;
      const response = await fetch(url);
      if (!response.ok) {
        // Mark as failed to prevent retries
        if (response.status === 404) {
          setFailedRuns(prev => new Set(prev).add(runId));
        }
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      const checkpoints = data.checkpoints || [];

      // Cache the result
      setCheckpointCache(prev => new Map(prev).set(runId, checkpoints));
      setFetchingRuns(prev => {
        const next = new Set(prev);
        next.delete(runId);
        return next;
      });

      return checkpoints;
    } catch (error) {
      console.error(`Failed to fetch checkpoints for run ${runId}:`, error);
      setFetchingRuns(prev => {
        const next = new Set(prev);
        next.delete(runId);
        return next;
      });
      return [];
    }
  }, [procedureName, failedRuns]);

  const handleCopyRun = useCallback(async (run: RunHistory) => {
    let checkpoints = run.checkpoints;

    if (!checkpoints && checkpointCache.has(run.id)) {
      checkpoints = checkpointCache.get(run.id);
    }

    if (!checkpoints && !fetchingRuns.has(run.id) && !failedRuns.has(run.id)) {
      setFetchingRuns(prev => new Set(prev).add(run.id));
      checkpoints = await fetchCheckpointsForRun(run.id);
    }

    const runWithCheckpoints: RunHistory = {
      ...run,
      checkpoints,
    };

    const yamlOutput = serializeRunToYaml(runWithCheckpoints);
    await copyTextToClipboard(yamlOutput);
  }, [checkpointCache, failedRuns, fetchingRuns, fetchCheckpointsForRun]);

  // Merge checkpoint data from cache into results history
  const resultsWithCheckpoints = React.useMemo(() => {
    if (!resultsHistory) {
      return resultsHistory;
    }

    return {
      ...resultsHistory,
      runs: resultsHistory.runs.map((run) => {
        const checkpoints = checkpointCache.get(run.id);
        return {
          ...run,
          checkpoints: checkpoints || undefined,
        };
      })
    };
  }, [resultsHistory, checkpointCache]);

  // Auto-fetch checkpoints for expanded runs
  useEffect(() => {
    if (!resultsHistory) return;

    resultsHistory.runs.forEach((run) => {
      if (run.isExpanded && !checkpointCache.has(run.id) && !fetchingRuns.has(run.id) && !failedRuns.has(run.id)) {
        setFetchingRuns(prev => new Set(prev).add(run.id));
        fetchCheckpointsForRun(run.id);
      }
    });
  }, [resultsHistory, checkpointCache, fetchingRuns, failedRuns, fetchCheckpointsForRun]);

  // Auto-scroll to bottom when content changes (new runs or new events)
  useEffect(() => {
    // Only auto-scroll if:
    // 1. We're on the Results tab
    // 2. The user hasn't manually scrolled away from bottom
    // 3. There's content to scroll
    if (activeTab === 'results' &&
        shouldAutoScrollRef.current &&
        resultsContentRef.current) {
      // Use setTimeout with requestAnimationFrame to ensure DOM has fully updated
      setTimeout(() => {
        requestAnimationFrame(() => {
          if (resultsContentRef.current) {
            resultsContentRef.current.scrollTop = resultsContentRef.current.scrollHeight;
          }
        });
      }, 50);
    }
  }, [resultsHistory, activeTab]); // Trigger on any resultsHistory change

  // Track run count changes separately (for initial scroll on new runs)
  useEffect(() => {
    const currentRunCount = resultsHistory?.runs.length || 0;

    // When a new run is added, always scroll to bottom regardless of user scroll position
    if (currentRunCount > lastRunCountRef.current) {
      shouldAutoScrollRef.current = true;

      if (activeTab === 'results' && resultsContentRef.current) {
        setTimeout(() => {
          requestAnimationFrame(() => {
            if (resultsContentRef.current) {
              resultsContentRef.current.scrollTop = resultsContentRef.current.scrollHeight;
            }
          });
        }, 50);
      }
    }

    lastRunCountRef.current = currentRunCount;
  }, [resultsHistory?.runs?.length, activeTab]);

  // Detect manual scrolling
  const handleScroll = () => {
    if (resultsContentRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = resultsContentRef.current;
      const isAtBottom = Math.abs(scrollHeight - clientHeight - scrollTop) < 50;
      shouldAutoScrollRef.current = isAtBottom;
    }
  };

  // When switching to Results tab, enable auto-scroll
  useEffect(() => {
    if (activeTab === 'results') {
      shouldAutoScrollRef.current = true;
      // Scroll to bottom when switching to Results tab
      if (resultsContentRef.current) {
        setTimeout(() => {
          if (resultsContentRef.current) {
            resultsContentRef.current.scrollTop = resultsContentRef.current.scrollHeight;
          }
        }, 50);
      }
    }
  }, [activeTab]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(value) => onTabChange(value as 'procedure' | 'results' | 'chat')} className="flex flex-col flex-1 min-h-0">
        <div className="flex items-center justify-between px-2 h-10 border-b bg-muted/30 flex-shrink-0">
            <TabsList className="h-8 bg-transparent p-0 gap-1">
              <TabsTrigger value="procedure" className="text-sm h-8 data-[state=active]:bg-background data-[state=active]:shadow-none">
                Procedure
              </TabsTrigger>
              <TabsTrigger value="results" className="text-sm h-8 data-[state=active]:bg-background data-[state=active]:shadow-none">
                Results
              </TabsTrigger>
              <TabsTrigger value="chat" className="text-sm h-8 data-[state=active]:bg-background data-[state=active]:shadow-none">
                <MessageSquare className="h-3.5 w-3.5 mr-1.5" />
                Chat
              </TabsTrigger>
            </TabsList>

            {/* Status indicators - only show on Results tab */}
            {activeTab === 'results' && (
              <div className="flex items-center gap-2">
                {isRunning && containerStatus.status === 'idle' && (
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Running...</span>
                  </div>
                )}
                {containerStatus.status === 'starting' && (
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Starting...</span>
                  </div>
                )}
                {containerStatus.status === 'ready' && (
                  <div className="flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400">
                    <Monitor className="h-3.5 w-3.5" />
                    <span>Ready ({(containerStatus.spinupMs! / 1000).toFixed(1)}s)</span>
                  </div>
                )}
                {containerStatus.status === 'disabled' && isRunning && (
                  <div className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    <span>No sandbox</span>
                  </div>
                )}
                {containerStatus.status === 'error' && (
                  <div className="flex items-center gap-1.5 text-xs text-destructive">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    <span>Error</span>
                  </div>
                )}
              </div>
            )}
        </div>

        {/* Tab Content Container - uses relative positioning for absolute TabsContent children */}
        <div className="flex-1 relative min-h-0">
          {/* Procedure Tab Content */}
          <TabsContent value="procedure" className="absolute inset-0 m-0 data-[state=inactive]:pointer-events-none">
            <ProcedureTab metadata={procedureMetadata} loading={metadataLoading} />
          </TabsContent>

          {/* Results Tab Content */}
          <TabsContent value="results" className="absolute inset-0 m-0 flex flex-col overflow-hidden data-[state=inactive]:pointer-events-none">
            {!resultsWithCheckpoints || resultsWithCheckpoints.runs.length === 0 ? (
              <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
                No results yet
              </div>
            ) : (
              <div ref={resultsContentRef} className="h-full overflow-y-auto" onScroll={handleScroll}>
                {resultsWithCheckpoints.runs.map((run) => (
                  <CollapsibleRun
                    key={run.id}
                    run={run}
                    isExpanded={run.isExpanded}
                    onToggle={() => onToggleRunExpansion(run.id)}
                    onCopyRun={handleCopyRun}
                    onJumpToSource={onJumpToSource}
                    onHITLRespond={onHITLRespond}
                  />
                ))}
              </div>
            )}
          </TabsContent>

          {/* Chat Tab Content */}
          <TabsContent value="chat" className="absolute inset-0 m-0 data-[state=inactive]:pointer-events-none">
            <ChatSidebar apiUrl={(path) => path} workspaceRoot={workspaceRoot} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
};
