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
  BarChart2
} from 'lucide-react';
import { MessageFeed } from './MessageFeed';

interface CollapsibleRunProps {
  run: RunHistory;
  isExpanded: boolean;
  onToggle: () => void;
}

export const CollapsibleRun: React.FC<CollapsibleRunProps> = ({ run, isExpanded, onToggle }) => {
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
      <button
        onClick={onToggle}
        className="w-full px-3 py-2 flex items-center justify-between hover:bg-muted/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">{operationIcon}</span>
          {statusIcon}
          <span className="text-sm font-medium capitalize">{run.operationType}</span>
          <span className="text-xs text-muted-foreground">{formatTimestamp(run.timestamp)}</span>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {isExpanded && run.events.length > 0 && (
        <div className="border-t border-border/30">
          <MessageFeed events={run.events} clustered={true} showFullLogs={false} />
        </div>
      )}

      {isExpanded && run.events.length === 0 && (
        <div className="px-3 py-4 text-sm text-muted-foreground text-center border-t border-border/30">
          No events yet
        </div>
      )}
    </div>
  );
};
