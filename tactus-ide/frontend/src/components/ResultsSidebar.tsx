import React, { useRef, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { FileResultsHistory } from '@/types/results';
import { ProcedureMetadata } from '@/types/metadata';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ProcedureTab } from './ProcedureTab';
import { CollapsibleRun } from './CollapsibleRun';

interface ResultsSidebarProps {
  currentFile: string | null;
  activeTab: 'procedure' | 'results';
  onTabChange: (tab: 'procedure' | 'results') => void;

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

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(value) => onTabChange(value as 'procedure' | 'results')} className="flex flex-col h-full">
        <div className="h-10 px-2 border-b flex items-center justify-between bg-muted/30 flex-shrink-0">
          <TabsList className="h-8">
            <TabsTrigger value="procedure" className="text-xs">
              Procedure
            </TabsTrigger>
            <TabsTrigger value="results" className="text-xs">
              Results
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
      </Tabs>
    </div>
  );
};
