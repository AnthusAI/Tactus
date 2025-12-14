import React, { useState, useEffect } from 'react';
import { LogEvent } from '@/types/events';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { LogEventComponent } from './LogEventComponent';
import { cn } from '@/lib/utils';
import { BaseEventComponent } from './BaseEventComponent';

interface LogClusterProps {
  events: LogEvent[];
  showFullLogs?: boolean;
  isAlternate?: boolean;
}

export const LogCluster: React.FC<LogClusterProps> = ({ events, showFullLogs = false, isAlternate }) => {
  const [isExpanded, setIsExpanded] = useState(showFullLogs);

  // Update expanded state when showFullLogs changes
  useEffect(() => {
    setIsExpanded(showFullLogs);
  }, [showFullLogs]);

  if (events.length === 0) {
    return null;
  }

  // If only one log, always show it expanded
  if (events.length === 1) {
    return <LogEventComponent event={events[0]} isAlternate={isAlternate} />;
  }

  // Count logs by level
  const levelCounts = events.reduce((acc, log) => {
    acc[log.level] = (acc[log.level] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const levelSummary = Object.entries(levelCounts)
    .map(([level, count]) => `${count} ${level.toLowerCase()}`)
    .join(', ');

  return (
    <BaseEventComponent isAlternate={isAlternate}>
      {/* Collapsed header */}
      {!isExpanded && (
        <button
          onClick={() => setIsExpanded(true)}
          className="w-full py-2 px-3 flex items-center gap-2 hover:bg-muted/30 transition-colors text-left"
        >
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            {events.length} log messages ({levelSummary})
          </span>
        </button>
      )}

      {/* Expanded content */}
      {isExpanded && (
        <div className={cn('overflow-hidden transition-all duration-300 ease-in-out')}>
          <button
            onClick={() => setIsExpanded(false)}
            className="w-full py-2 px-3 flex items-center gap-2 hover:bg-muted/30 transition-colors text-left border-b border-border/50"
          >
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">
              {events.length} log messages ({levelSummary})
            </span>
          </button>
          <div className="animate-in slide-in-from-top-2 duration-300">
            {events.map((log, index) => (
              <LogEventComponent key={`${log.timestamp}-${index}`} event={log} />
            ))}
          </div>
        </div>
      )}
    </BaseEventComponent>
  );
};





