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
      try {
        const event = JSON.parse(e.data) as AnyEvent;
        
        setEvents((prev) => [...prev, event]);
        
        // Check if execution is complete
        if (event.event_type === 'execution' && 
            (event.lifecycle_stage === 'complete' || event.lifecycle_stage === 'error')) {
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
        console.error('Error parsing SSE event:', err);
        setError('Failed to parse event data');
      }
    };

    eventSource.onerror = (err) => {
      console.error('SSE error:', err);
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



