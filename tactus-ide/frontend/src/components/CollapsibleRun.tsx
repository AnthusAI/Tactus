import React from 'react';
import { RunHistory } from '@/types/results';
import {
  ChevronDown,
  ChevronUp,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
  IterationCw,
  TestTube,
  BarChart2,
  ArrowUpRight,
  Copy
} from 'lucide-react';
import { MessageFeed } from './MessageFeed';
import { CheckpointSummary } from './CheckpointSummary';
import { ProcedureInputsDisplay } from './ProcedureInputsDisplay';

interface CollapsibleRunProps {
  run: RunHistory;
  isExpanded: boolean;
  onToggle: () => void;
  onCopyRun?: (run: RunHistory) => void;
  onJumpToSource?: (filePath: string, lineNumber: number) => void;
  onHITLRespond?: (requestId: string, value: any) => void;
}

export const CollapsibleRun: React.FC<CollapsibleRunProps> = ({ run, isExpanded, onToggle, onCopyRun, onJumpToSource, onHITLRespond }) => {
  // Operation type icons
  const operationIcon = {
    run: <IterationCw className="h-4 w-4" />,
    test: <TestTube className="h-4 w-4" />,
    evaluate: <BarChart2 className="h-4 w-4" />,
    validate: <CheckCircle className="h-4 w-4" />,
  }[run.operationType];

  // Status icons with colors
  const statusIcon = {
    running: <Loader2 className="h-4 w-4 animate-spin text-blue-500" />,
    success: <CheckCircle className="h-4 w-4 text-green-500" />,
    failed: <XCircle className="h-4 w-4 text-red-500" />,
    error: <AlertCircle className="h-4 w-4 text-red-500" />,
  }[run.status];

  // Find the most recent checkpoint with a source location
  const latestCheckpointWithSource = run.checkpoints?.find(cp => cp.source_location);

  const formatTimestamp = (timestamp: string) => {
    // Handle both Unix timestamp (number as string) and ISO string formats
    let date: Date;
    if (/^\d+(\.\d+)?$/.test(timestamp)) {
      // Unix timestamp - convert to milliseconds
      date = new Date(parseFloat(timestamp) * 1000);
    } else {
      // ISO string
      date = new Date(timestamp);
    }
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="border-b border-border/50">
      <div className="flex items-center">
        <button
          onClick={onToggle}
          className="flex-1 px-3 py-2 flex items-center justify-between hover:bg-muted/30 transition-colors"
        >
          <div className="flex items-center gap-2">
            {statusIcon}
            <span className="text-sm font-medium capitalize">{run.operationType}</span>
            <span className="text-xs text-muted-foreground">{formatTimestamp(run.timestamp)}</span>
            <span className="text-muted-foreground">{operationIcon}</span>
            {onCopyRun && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onCopyRun(run);
                }}
                className="px-1.5 py-1 rounded hover:bg-muted/60 transition-colors"
                title="Copy run log"
              >
                <Copy className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
              </button>
            )}
            {!isExpanded && run.checkpoints && run.checkpoints.length > 0 && (
              <>
                <span className="text-xs text-muted-foreground">•</span>
                <span className="text-xs text-muted-foreground">
                  {run.checkpoints.length} checkpoint{run.checkpoints.length !== 1 ? 's' : ''}
                </span>
              </>
            )}
          </div>
          {isExpanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>
        {/* Jump to Source button in collapsed state */}
        {!isExpanded && latestCheckpointWithSource && onJumpToSource && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onJumpToSource(
                latestCheckpointWithSource.source_location!.file,
                latestCheckpointWithSource.source_location!.line
              );
            }}
            className="px-2 py-2 hover:bg-muted/30 transition-colors border-l border-border/30"
            title={`Jump to ${latestCheckpointWithSource.source_location!.file.split('/').pop()}:${latestCheckpointWithSource.source_location!.line}`}
          >
            <ArrowUpRight className="h-4 w-4 text-muted-foreground hover:text-foreground" />
          </button>
        )}
      </div>

      {/* Show inputs at top of expanded run if available */}
      {isExpanded && run.inputs && Object.keys(run.inputs).length > 0 && (
        <ProcedureInputsDisplay inputs={run.inputs} />
      )}

      {isExpanded && run.events.length > 0 && (
        <div className="border-t border-border/30">
          <MessageFeed events={run.events} clustered={false} showFullLogs={false} onJumpToSource={onJumpToSource} onHITLRespond={onHITLRespond} />
        </div>
      )}

      {isExpanded && run.events.length === 0 && (
        <div className="px-3 py-4 text-sm text-muted-foreground text-center border-t border-border/30">
          No events yet
        </div>
      )}

      {isExpanded && run.checkpoints && run.checkpoints.length > 0 && (
        <CheckpointSummary checkpoints={run.checkpoints} onJumpToSource={onJumpToSource} />
      )}

      {isExpanded && (
        <div style={{ display: 'none' }}>
          Debug: checkpoints={JSON.stringify({ hasCheckpoints: !!run.checkpoints, count: run.checkpoints?.length })}
        </div>
      )}
    </div>
  );
};
