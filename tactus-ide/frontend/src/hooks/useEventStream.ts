/**
 * React hook for consuming Server-Sent Events (SSE) from the backend.
 * 
 * Manages EventSource connection lifecycle and accumulates events.
 * Supports both GET (EventSource) and POST (fetch streaming) requests.
 */

import { useState, useEffect, useRef } from 'react';
import { flushSync } from 'react-dom';
import { AnyEvent } from '@/types/events';

interface StreamState {
  events: AnyEvent[];
  isRunning: boolean;
  error: string | null;
}

interface PostStreamConfig {
  url: string;
  method: 'POST';
  body: any;
}

/**
 * Helper to update events with a new streaming chunk.
 * Extracts the logic for handling agent_stream_chunk events.
 */
function updateEventsWithStreamChunk(prev: AnyEvent[], event: AnyEvent): AnyEvent[] {
  const chunkEvent = event as any;

  // Convert loading event to "completed" state on first chunk
  const updated = prev.map(e => {
    if (e.event_type === 'loading') {
      const loadingMsg = (e as any).message;
      if (loadingMsg === `Waiting for ${chunkEvent.agent_name} response...`) {
        const loadingTime = new Date(e.timestamp).getTime();
        const chunkTime = new Date(chunkEvent.timestamp).getTime();
        const durationMs = chunkTime - loadingTime;
        return {
          ...e,
          message: `${chunkEvent.agent_name} response received`,
          completed: true,
          duration_ms: durationMs,
        };
      }
    }
    return e;
  });

  // Remove previous stream chunks for this agent
  const filtered = updated.filter(e => {
    if (e.event_type === 'agent_stream_chunk') {
      const prevChunk = e as any;
      return prevChunk.agent_name !== chunkEvent.agent_name;
    }
    return true;
  });

  return [...filtered, event];
}

export function useEventStream(url: string | null): StreamState {
  const [events, setEvents] = useState<AnyEvent[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // If no URL, clean up and reset
    if (!url) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
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

    // Shared event handler for both GET and POST streams
    const handleEvent = (event: AnyEvent) => {
      // #region agent log
      console.log('[SSE] Event parsed:', {event_type: event.event_type, lifecycle_stage: event.lifecycle_stage, has_response_data: event.event_type === 'cost' ? !!(event as any).response_data : undefined, agent_name: (event as any).agent_name});
      // #endregion

      // Use flushSync for streaming chunks to force immediate rendering
      // This prevents React from batching updates and displaying all chunks at once
      if (event.event_type === 'agent_stream_chunk') {
        flushSync(() => {
          setEvents((prev) => updateEventsWithStreamChunk(prev, event));
        });
        return;
      }

      setEvents((prev) => {
        // #region agent log
        console.log('[SSE] Adding event to state, prev count:', prev.length);
        // #endregion

        // Streaming chunks are now handled with flushSync above, this should never be reached

        // Clear pending HITL requests when a new execution starts
        // This prevents stale HITL events from previous runs from being clickable
        if (event.event_type === 'execution') {
          const execEvent = event as any;
          if (execEvent.lifecycle_stage === 'start') {
            console.log('[SSE] New execution started, clearing pending HITL events');
            // Filter out unanswered HITL requests (those without a "responded" marker)
            const filtered = prev.filter(e => {
              if (e.event_type === 'hitl.request') {
                // Keep HITL events that have been responded to (marked by HITLEventComponent)
                // This check relies on the component's internal state, but we can't access it here
                // Instead, we'll just clear ALL HITL requests on new execution start
                return false;
              }
              return true;
            });
            return [...filtered, event];
          }
        }

        // If this is a cost event, update loading events to completed state (but KEEP streaming chunks visible)
        if (event.event_type === 'cost') {
          const costEvent = event as any;
          // #region agent log
          console.log('[SSE] Cost event received:', JSON.stringify({agent_name: costEvent.agent_name, has_response_data: !!costEvent.response_data, response_data_keys: costEvent.response_data ? Object.keys(costEvent.response_data) : null, response_data: costEvent.response_data}));
          // #endregion
          const updated = prev.map(e => {
            // Convert loading event to "completed" state if not already done by streaming
            if (e.event_type === 'loading' && !(e as any).completed) {
              const loadingMsg = (e as any).message;
              if (loadingMsg === `Waiting for ${costEvent.agent_name} response...`) {
                // Calculate duration from loading event timestamp to cost event
                const loadingTime = new Date(e.timestamp).getTime();
                const costTime = new Date(costEvent.timestamp).getTime();
                const durationMs = costTime - loadingTime;
                // #region agent log
                console.log('[SSE] Converting loading event to completed:', loadingMsg, 'duration:', durationMs);
                // #endregion
                return {
                  ...e,
                  message: `${costEvent.agent_name} response received`,
                  completed: true,
                  duration_ms: durationMs,
                };
              }
            }
            return e;
          });
          // Remove agent_turn started events for this agent
          const filtered = updated.filter(e => {
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

        // Convert agent_turn started events to loading events so they can be tracked/completed
        if (event.event_type === 'agent_turn') {
          const turnEvent = event as any;
          if (turnEvent.stage === 'started') {
            // Create a loading event instead of adding the agent_turn event
            const loadingEvent = {
              event_type: 'loading',
              message: `Waiting for ${turnEvent.agent_name} response...`,
              timestamp: turnEvent.timestamp,
              procedure_id: turnEvent.procedure_id,
              completed: false,
            };
            console.log('[SSE] Converting agent_turn started to loading event:', turnEvent.agent_name);
            return [...prev, loadingEvent];
          }
          // Don't add agent_turn completed events (they're redundant with cost events)
          return prev;
        }

        // Handle container_status events - update "starting" to "completed" when "running" arrives
        if (event.event_type === 'container_status') {
          const containerEvent = event as any;

          if (containerEvent.status === 'running') {
            // Find the "starting" event and update it to show completion with duration
            const updated = prev.map(e => {
              if (e.event_type === 'container_status' && (e as any).status === 'starting') {
                const startTime = new Date(e.timestamp).getTime();
                const runningTime = new Date(containerEvent.timestamp).getTime();
                const durationMs = runningTime - startTime;
                console.log('[SSE] Container started, duration:', durationMs, 'ms');
                return {
                  ...e,
                  status: 'started',  // New status to indicate completion
                  completed: true,
                  duration_ms: durationMs,
                };
              }
              return e;
            });
            // Don't add the "running" event - we've updated "starting" to show completion
            return updated;
          }

          // For "starting" and other statuses, add the event normally
          return [...prev, event];
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
          if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
          }
        }, 500);
      }
    };

    // Check if this is a POST request config (JSON string)
    let postConfig: PostStreamConfig | null = null;
    try {
      const parsed = JSON.parse(url);
      if (parsed.method === 'POST' && parsed.url && parsed.body) {
        postConfig = parsed;
      }
    } catch {
      // Not JSON, treat as regular GET URL
    }

    if (postConfig) {
      // Use fetch streaming for POST requests
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      (async () => {
        try {
          const response = await fetch(postConfig.url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(postConfig.body),
            signal: abortController.signal,
          });

          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }

          const reader = response.body?.getReader();
          if (!reader) {
            throw new Error('No response body');
          }

          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const data = line.slice(6);
                try {
                  const event = JSON.parse(data) as AnyEvent;
                  handleEvent(event);
                } catch (err) {
                  console.error('Error parsing SSE event:', err);
                }
              }
            }
          }

          setIsRunning(false);
        } catch (err: any) {
          if (err.name === 'AbortError') {
            console.debug('Fetch stream aborted');
          } else {
            console.error('Fetch stream error:', err);
            setError('Connection error');
          }
          setIsRunning(false);
        }
      })();

      // Cleanup function
      return () => {
        if (abortControllerRef.current) {
          abortControllerRef.current.abort();
          abortControllerRef.current = null;
        }
      };
    } else {
      // Use EventSource for GET requests
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
          handleEvent(event);
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
    }
  }, [url]);

  return { events, isRunning, error };
}
