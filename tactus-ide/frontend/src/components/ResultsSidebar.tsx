import React, { useRef, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { FileResultsHistory } from '@/types/results';
import { ProcedureMetadata } from '@/types/metadata';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ProcedureTab } from './ProcedureTab';
import { CollapsibleRun } from './CollapsibleRun';
import { CheckpointList } from './debugger/CheckpointList';
import { CheckpointDetails } from './debugger/CheckpointDetails';
import { RunSelector } from './debugger/RunSelector';
import { StatisticsPanel } from './debugger/StatisticsPanel';
import { useRunList, useRun } from '../hooks/useTracing';

interface ResultsSidebarProps {
  currentFile: string | null;
  activeTab: 'procedure' | 'results' | 'checkpoints';
  onTabChange: (tab: 'procedure' | 'results' | 'checkpoints') => void;

  // Procedure tab
  procedureMetadata: ProcedureMetadata | null;
  metadataLoading: boolean;

  // Results tab
  resultsHistory: FileResultsHistory | null;
  isRunning: boolean;
  onToggleRunExpansion: (runId: string) => void;
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
}) => {
  const resultsContentRef = useRef<HTMLDivElement>(null);
  const lastRunCountRef = useRef<number>(0);
  const shouldAutoScrollRef = useRef<boolean>(true);

  // Checkpoints tab state
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedPosition, setSelectedPosition] = useState<number | null>(null);

  // Extract procedure name from current file path
  // The backend saves runs with "ide-{filename}" as the procedure_name
  const procedureName = currentFile
    ? `ide-${currentFile.split('/').pop()?.replace('.tac', '')}` || undefined
    : undefined;

  // Auto-refresh runs list every 3 seconds when on Results OR Checkpoints tab
  // Filter by current procedure name
  const { runs: persistedRuns, loading: runsLoading } = useRunList({
    procedure: procedureName,
    limit: 50,
    autoRefresh: activeTab === 'results' || activeTab === 'checkpoints',
    refreshInterval: 3000
  });
  const { run, loading: runLoading } = useRun(selectedRunId, procedureName);

  // Both tabs use the same data source
  const runs = persistedRuns;

  const selectedCheckpoint = run
    ? run.execution_log.find((cp) => cp.position === selectedPosition)
    : undefined;

  // Auto-scroll to bottom when NEW runs are added
  useEffect(() => {
    const currentRunCount = resultsHistory?.runs.length || 0;

    // Auto-scroll if the number of runs increased (new run added)
    if (activeTab === 'results' &&
        resultsContentRef.current &&
        currentRunCount > lastRunCountRef.current) {
      // Use setTimeout with requestAnimationFrame to ensure DOM has fully updated
      setTimeout(() => {
        requestAnimationFrame(() => {
          if (resultsContentRef.current) {
            resultsContentRef.current.scrollTop = resultsContentRef.current.scrollHeight;
          }
        });
      }, 50);
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

  // Get status text
  const getStatus = () => {
    if (isRunning) return 'Running...';
    if (!resultsHistory || resultsHistory.runs.length === 0) return 'Ready';

    // Check status of most recent run (last in array)
    const latestRun = resultsHistory.runs[resultsHistory.runs.length - 1];
    if (latestRun.status === 'success') return 'Completed';
    if (latestRun.status === 'failed') return 'Failed';
    if (latestRun.status === 'error') return 'Error';

    return 'Ready';
  };

  const handleRunSelect = (runId: string) => {
    setSelectedRunId(runId);
    setSelectedPosition(null);
  };

  const handleCheckpointSelect = (position: number) => {
    setSelectedPosition(position);
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(value) => onTabChange(value as 'procedure' | 'results' | 'checkpoints')} className="flex flex-col h-full">
        <div className="h-10 px-2 border-b flex items-center justify-between bg-muted/30 flex-shrink-0">
          <TabsList className="h-8">
            <TabsTrigger value="procedure" className="text-xs">
              Procedure
            </TabsTrigger>
            <TabsTrigger value="results" className="text-xs">
              Results
            </TabsTrigger>
            <TabsTrigger value="checkpoints" className="text-xs">
              Checkpoints
            </TabsTrigger>
          </TabsList>

          {activeTab === 'results' && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {isRunning && <Loader2 className="h-3 w-3 animate-spin" />}
              <span>{getStatus()}</span>
            </div>
          )}
        </div>

        {/* Procedure Tab Content */}
        <TabsContent value="procedure" className="h-0 flex-1 m-0">
          <ProcedureTab metadata={procedureMetadata} loading={metadataLoading} />
        </TabsContent>

        {/* Results Tab Content */}
        <TabsContent value="results" className="h-0 flex-1 m-0 overflow-hidden">
          {!resultsHistory || resultsHistory.runs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
              No results yet
            </div>
          ) : (
            <div ref={resultsContentRef} className="h-full overflow-y-auto" onScroll={handleScroll}>
              {resultsHistory.runs.map((run) => (
                <CollapsibleRun
                  key={run.id}
                  run={run}
                  isExpanded={run.isExpanded}
                  onToggle={() => onToggleRunExpansion(run.id)}
                />
              ))}
            </div>
          )}
        </TabsContent>

        {/* Checkpoints Tab Content */}
        <TabsContent value="checkpoints" className="h-0 flex-1 m-0 overflow-hidden flex flex-col">
          {/* Run Selector */}
          <div className="p-3 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
            <RunSelector
              runs={runs}
              selectedRunId={selectedRunId}
              onSelect={handleRunSelect}
              loading={runsLoading}
            />
          </div>

          {/* Content Area */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {runLoading ? (
              <div className="flex-1 flex items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : run ? (
              <>
                {/* Checkpoint List */}
                <div className="flex-1 overflow-hidden">
                  <CheckpointList
                    checkpoints={run.execution_log}
                    selectedPosition={selectedPosition}
                    onSelect={handleCheckpointSelect}
                  />
                </div>

                {/* Selected Checkpoint Details - shown when a checkpoint is selected */}
                {selectedCheckpoint && (
                  <div className="border-t border-gray-200 dark:border-gray-700 max-h-[50%] overflow-hidden flex flex-col">
                    <CheckpointDetails checkpoint={selectedCheckpoint} />
                  </div>
                )}

                {/* Statistics Panel - shown when no checkpoint is selected */}
                {!selectedCheckpoint && (
                  <div className="border-t border-gray-200 dark:border-gray-700">
                    <StatisticsPanel runId={run.run_id} procedure={procedureName} />
                  </div>
                )}
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
                Select a run to view checkpoints
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};
