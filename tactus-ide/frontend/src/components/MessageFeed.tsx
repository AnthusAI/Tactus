import React, { useMemo } from 'react';
import { AnyEvent, LogEvent } from '@/types/events';
import { EventRenderer } from './events/EventRenderer';
import { LogCluster } from './events/LogCluster';

interface MessageFeedProps {
  events: AnyEvent[];
  clustered?: boolean;
  showFullLogs?: boolean;
  onJumpToSource?: (filePath: string, lineNumber: number) => void;
  onHITLRespond?: (requestId: string, value: any) => void;
}

/**
 * Filter out agent_turn(started) events when we have streaming chunks, completed events, or cost events.
 * This prevents the "Waiting for X response..." spinner from showing alongside
 * actual streaming content or final responses.
 */
function filterSupersededLoadingEvents(events: AnyEvent[]): AnyEvent[] {
  // Debug: Log incoming events
  const eventTypes = events.map(e => e.event_type);
  const streamChunkCount = eventTypes.filter(t => t === 'agent_stream_chunk').length;
  if (streamChunkCount > 0) {
    console.log('[filterSupersededLoadingEvents] Input has', streamChunkCount, 'stream chunks out of', events.length, 'total events');
  }

  // Check if we have any content events (streaming chunks, completed turn, or cost events)
  const hasContent = events.some(event => {
    if (event.event_type === 'agent_stream_chunk' || event.event_type === 'cost') {
      return true;
    }
    // Also check for agent_turn(completed) events
    if (event.event_type === 'agent_turn') {
      const turnEvent = event as any;
      return turnEvent.stage === 'completed';
    }
    return false;
  });

  // If we have content, filter out all agent_turn(started) events
  if (hasContent) {
    return events.filter(event => {
      if (event.event_type === 'agent_turn') {
        const turnEvent = event as any;
        return turnEvent.stage !== 'started';
      }
      return true;
    });
  }

  return events;
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
  showFullLogs = false,
  onJumpToSource,
  onHITLRespond
}) => {
  const displayItems = useMemo(() => {
    // Filter out loading spinners when we have actual content
    const filteredEvents = filterSupersededLoadingEvents(events);

    // Debug: Log what we're displaying
    const streamChunks = filteredEvents.filter(e => e.event_type === 'agent_stream_chunk');
    if (streamChunks.length > 0) {
      console.log('[MessageFeed] Display items includes', streamChunks.length, 'stream chunks');
    }

    return clustered ? clusterEvents(filteredEvents) : filteredEvents;
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
              onJumpToSource={onJumpToSource}
              onHITLRespond={onHITLRespond}
            />
          );
        }
      })}
    </div>
  );
};
