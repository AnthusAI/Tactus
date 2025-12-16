/**
 * React hook for consuming Server-Sent Events (SSE) from the backend.
 * 
 * Manages EventSource connection lifecycle and accumulates events.
 */

import { useState, useEffect, useRef } from 'react';
import { AnyEvent } from '@/types/events';

interface StreamState {
  events: AnyEvent[];
  isRunning: boolean;
  error: string | null;
}

export function useEventStream(url: string | null): StreamState {
  const [events, setEvents] = useState<AnyEvent[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    // If no URL, clean up and reset
    if (!url) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setEvents([]);
      setError(null);
      setIsRunning(false);
      return;
    }

    // Clear previous events when starting new stream
    setEvents([]);
    setError(null);
    setIsRunning(true);

    // Create EventSource
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log('SSE connection opened');
    };

            eventSource.onmessage = (e) => {
              // #region agent log
              console.log('[SSE] Message received:', {data_length: e.data?.length, data_preview: e.data?.substring(0, 100)});
              // #endregion
              try {
                const event = JSON.parse(e.data) as AnyEvent;
                // #region agent log
                console.log('[SSE] Event parsed:', {event_type: event.event_type, lifecycle_stage: event.lifecycle_stage, has_response_data: event.event_type === 'cost' ? !!(event as any).response_data : undefined, agent_name: (event as any).agent_name});
                // #endregion

                setEvents((prev) => {
                  // #region agent log
                  console.log('[SSE] Adding event to state, prev count:', prev.length);
                  // #endregion
                  
                  // If this is a streaming chunk event, replace loading and previous chunks for this agent
                  if (event.event_type === 'agent_stream_chunk') {
                    const chunkEvent = event as any;
                    const filtered = prev.filter(e => {
                      // Remove loading events that match this agent
                      if (e.event_type === 'loading') {
                        const loadingMsg = (e as any).message;
                        return loadingMsg !== `Waiting for ${chunkEvent.agent_name} response...`;
                      }
                      // Remove previous stream chunks for this agent
                      if (e.event_type === 'agent_stream_chunk') {
                        const prevChunk = e as any;
                        return prevChunk.agent_name !== chunkEvent.agent_name;
                      }
                      return true;
                    });
                    return [...filtered, event];
                  }
                  
                  // If this is a cost event, remove loading and agent_turn events (but KEEP streaming chunks visible)
                  if (event.event_type === 'cost') {
                    const costEvent = event as any;
                    // #region agent log
                    console.log('[SSE] Cost event received:', JSON.stringify({agent_name: costEvent.agent_name, has_response_data: !!costEvent.response_data, response_data_keys: costEvent.response_data ? Object.keys(costEvent.response_data) : null, response_data: costEvent.response_data}));
                    // #endregion
                    const filtered = prev.filter(e => {
                      // Remove loading events that match this agent
                      if (e.event_type === 'loading') {
                        const loadingMsg = (e as any).message;
                        const shouldRemove = loadingMsg === `Waiting for ${costEvent.agent_name} response...`;
                        // #region agent log
                        if (shouldRemove) console.log('[SSE] Removing loading event:', loadingMsg);
                        // #endregion
                        return !shouldRemove;
                      }
                      // Remove agent_turn started events for this agent
                      if (e.event_type === 'agent_turn') {
                        const turnEvent = e as any;
                        const shouldRemove = turnEvent.agent_name === costEvent.agent_name && turnEvent.stage === 'started';
                        // #region agent log
                        if (shouldRemove) console.log('[SSE] Removing agent_turn started event:', turnEvent.agent_name);
                        // #endregion
                        return !shouldRemove;
                      }
                      return true;
                    });
                    // Don't show response_data in CostEvent if we streamed it
                    // Check if there's a streaming chunk for this agent
                    const hasStreamChunk = prev.some(e => 
                      e.event_type === 'agent_stream_chunk' && 
                      (e as any).agent_name === costEvent.agent_name
                    );
                    if (hasStreamChunk && costEvent.response_data) {
                      // Hide response_data since we already streamed it
                      costEvent.response_data = null;
                    }
                    return [...filtered, event];
                  }
                  
                  return [...prev, event];
                });
        
        // Check if execution is complete
        const isExecutionComplete =
          (event.event_type === 'execution' &&
           (event.lifecycle_stage === 'complete' || event.lifecycle_stage === 'error')) ||
          event.event_type === 'test_completed' ||
          event.event_type === 'evaluation_completed';

        if (isExecutionComplete) {
          // #region agent log
          console.log('[SSE] Execution complete, closing connection');
          // #endregion
          setIsRunning(false);
          // Close the connection after a short delay to ensure all events are received
          setTimeout(() => {
            if (eventSourceRef.current) {
              eventSourceRef.current.close();
              eventSourceRef.current = null;
            }
          }, 500);
        }
      } catch (err) {
        // #region agent log
        console.error('[SSE] Parse error:', err, 'data:', e.data);
        // #endregion
        console.error('Error parsing SSE event:', err);
        setError('Failed to parse event data');
      }
    };

    eventSource.onerror = (err) => {
      // #region agent log
      console.debug('[SSE] Error event:', {readyState: eventSource.readyState, err, type: err.type, target: err.target});
      // #endregion
      
      // If connection is already closed (readyState 2), this is expected after completion
      if (eventSource.readyState === EventSource.CLOSED) {
        console.debug('SSE connection closed (expected after completion)');
        return;
      }
      
      // If we're connecting (readyState 0), this might be a temporary connection issue
      if (eventSource.readyState === EventSource.CONNECTING) {
        console.debug('SSE reconnecting...');
        return;
      }
      
      // Only log actual errors
      console.error('SSE error:', err, 'readyState:', eventSource.readyState);
      setError('Connection error');
      setIsRunning(false);
      eventSource.close();
      eventSourceRef.current = null;
    };

    // Cleanup on unmount or URL change
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [url]);

  return { events, isRunning, error };
}





