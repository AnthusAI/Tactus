import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronUp, X, Loader2, Copy, Check } from 'lucide-react';
import { AnyEvent, LogEvent } from '@/types/events';
import { EventRenderer } from './events/EventRenderer';
import { LogCluster } from './events/LogCluster';
import { exportEventsForAI } from '@/utils/exportForAI';

interface ResultsSidebarProps {
  events: AnyEvent[];
  isRunning: boolean;
  onClear: () => void;
}

/**
 * Cluster consecutive log events together.
 * Returns an array where each element is either:
 * - An array of LogEvent (a cluster)
 * - A single non-log event
 */
function clusterEvents(events: AnyEvent[]): (LogEvent[] | AnyEvent)[] {
  const clusters: (LogEvent[] | AnyEvent)[] = [];
  let currentLogCluster: LogEvent[] = [];

  for (const event of events) {
    if (event.event_type === 'log') {
      currentLogCluster.push(event as LogEvent);
    } else {
      // Non-log event: flush current cluster and add this event
      if (currentLogCluster.length > 0) {
        clusters.push(currentLogCluster);
        currentLogCluster = [];
      }
      clusters.push(event);
    }
  }

  // Flush any remaining log cluster
  if (currentLogCluster.length > 0) {
    clusters.push(currentLogCluster);
  }

  return clusters;
}

export const ResultsSidebar: React.FC<ResultsSidebarProps> = ({ events, isRunning, onClear }) => {
  const [showFullLogs, setShowFullLogs] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
  const [copied, setCopied] = useState(false);

  // Cluster events
  const clusteredEvents = useMemo(() => clusterEvents(events), [events]);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (shouldAutoScroll && contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [events, shouldAutoScroll]);

  // Check if user has scrolled up (disable auto-scroll)
  const handleScroll = () => {
    if (contentRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = contentRef.current;
      const isAtBottom = Math.abs(scrollHeight - clientHeight - scrollTop) < 10;
      setShouldAutoScroll(isAtBottom);
    }
  };

  // Get status text
  const getStatus = () => {
    if (isRunning) return 'Running...';
    if (events.length === 0) return 'Ready';
    
    // Check last event
    const lastEvent = events[events.length - 1];
    if (lastEvent.event_type === 'execution') {
      if (lastEvent.lifecycle_stage === 'complete') return 'Completed';
      if (lastEvent.lifecycle_stage === 'error') return 'Failed';
    }
    
    return 'Ready';
  };

  const handleCopyForAI = async () => {
    const exportedData = exportEventsForAI(events);
    try {
      await navigator.clipboard.writeText(exportedData);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="h-8 px-2 border-b flex items-center justify-between bg-muted/30 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowFullLogs(!showFullLogs)}
            className="h-6 text-xs"
          >
            {showFullLogs ? <ChevronUp className="h-3 w-3 mr-1" /> : <ChevronDown className="h-3 w-3 mr-1" />}
            Show Full Logs
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopyForAI}
            className="h-6 text-xs"
            disabled={events.length === 0}
            title="Copy results in AI-comprehensible format (YAML)"
          >
            {copied ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
            {copied ? 'Copied!' : 'Copy for AI'}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClear}
            className="h-6 text-xs"
            disabled={events.length === 0}
          >
            <X className="h-3 w-3 mr-1" />
            Clear
          </Button>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {isRunning && <Loader2 className="h-3 w-3 animate-spin" />}
          <span>{getStatus()}</span>
        </div>
      </div>

      {/* Content area */}
      <div
        ref={contentRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto"
      >
        {events.length === 0 ? (
          <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
            No results yet
          </div>
        ) : (
          <div>
            {clusteredEvents.map((item, index) => {
              if (Array.isArray(item)) {
                // It's a log cluster
                return <LogCluster key={`cluster-${index}`} logs={item} forceExpanded={showFullLogs} />;
              } else {
                // It's a single non-log event
                return <EventRenderer key={`event-${index}`} event={item} />;
              }
            })}
          </div>
        )}
      </div>

      {/* Scroll to bottom button (when not auto-scrolling) */}
      {!shouldAutoScroll && events.length > 0 && (
        <div className="absolute bottom-4 right-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setShouldAutoScroll(true);
              if (contentRef.current) {
                contentRef.current.scrollTop = contentRef.current.scrollHeight;
              }
            }}
            className="h-8 shadow-lg"
          >
            <ChevronDown className="h-4 w-4 mr-1" />
            Scroll to bottom
          </Button>
        </div>
      )}
    </div>
  );
};



