import React, { useMemo } from 'react';
import { AnyEvent, LogEvent } from '@/types/events';
import { EventRenderer } from './events/EventRenderer';
import { LogCluster } from './events/LogCluster';

interface MessageFeedProps {
  events: AnyEvent[];
  clustered?: boolean;
  showFullLogs?: boolean;
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

export const MessageFeed: React.FC<MessageFeedProps> = ({ 
  events, 
  clustered = false,
  showFullLogs = false 
}) => {
  const displayItems = useMemo(() => {
    return clustered ? clusterEvents(events) : events;
  }, [events, clustered]);

  return (
    <div className="flex flex-col">
      {displayItems.map((item, index) => {
        const isAlternate = index % 2 === 1;
        
        if (Array.isArray(item)) {
          // It's a log cluster
          return (
            <LogCluster 
              key={index} 
              events={item} 
              showFullLogs={showFullLogs}
              isAlternate={isAlternate}
            />
          );
        } else {
          // It's a single event
          return (
            <EventRenderer 
              key={index} 
              event={item} 
              isAlternate={isAlternate}
            />
          );
        }
      })}
    </div>
  );
};
