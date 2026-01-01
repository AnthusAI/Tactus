/**
 * React hooks for accessing execution tracing data via the backend API.
 */

import { useState, useEffect, useCallback } from 'react';
import type {
  ExecutionRun,
  RunListItem,
  CheckpointEntry,
  RunStatistics,
  Breakpoint,
  ComparisonResult,
} from '../types/tracing';

// Use VITE_BACKEND_URL if available, otherwise use relative URLs
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
const API_BASE = `${BACKEND_URL}/api/traces`;

/**
 * Hook for listing execution runs.
 */
export function useRunList(options?: {
  procedure?: string;
  status?: string;
  limit?: number;
  autoRefresh?: boolean;
  refreshInterval?: number;
}) {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRuns = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (options?.procedure) params.append('procedure', options.procedure);
      if (options?.status) params.append('status', options.status);
      if (options?.limit) params.append('limit', options.limit.toString());

      const response = await fetch(`${API_BASE}/runs?${params}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data = await response.json();
      setRuns(data.runs || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch runs');
    } finally {
      setLoading(false);
    }
  }, [options?.procedure, options?.status, options?.limit]);

  useEffect(() => {
    fetchRuns();

    // Auto-refresh if enabled
    if (options?.autoRefresh) {
      const interval = setInterval(fetchRuns, options.refreshInterval || 5000);
      return () => clearInterval(interval);
    }
  }, [fetchRuns, options?.autoRefresh, options?.refreshInterval]);

  return { runs, loading, error, refetch: fetchRuns };
}

/**
 * Hook for getting a specific execution run.
 */
export function useRun(runId: string | null, procedure?: string) {
  const [run, setRun] = useState<ExecutionRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId || !procedure) {
      setRun(null);
      return;
    }

    const fetchRun = async () => {
      try {
        setLoading(true);
        const url = `${API_BASE}/runs/${runId}?procedure=${encodeURIComponent(procedure)}`;
        const response = await fetch(url);
        if (!response.ok) {
          if (response.status === 404) {
            throw new Error('Run not found');
          }
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        setRun(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch run');
        setRun(null);
      } finally {
        setLoading(false);
      }
    };

    fetchRun();
  }, [runId, procedure]);

  return { run, loading, error };
}

/**
 * Hook for getting a specific checkpoint.
 */
export function useCheckpoint(runId: string | null, position: number | null) {
  const [checkpoint, setCheckpoint] = useState<CheckpointEntry | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId || position === null) {
      setCheckpoint(null);
      return;
    }

    const fetchCheckpoint = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${API_BASE}/runs/${runId}/checkpoints/${position}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        setCheckpoint(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch checkpoint');
        setCheckpoint(null);
      } finally {
        setLoading(false);
      }
    };

    fetchCheckpoint();
  }, [runId, position]);

  return { checkpoint, loading, error };
}

/**
 * Hook for getting run statistics.
 */
export function useRunStatistics(runId: string | null, procedure?: string) {
  const [statistics, setStatistics] = useState<RunStatistics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId || !procedure) {
      setStatistics(null);
      return;
    }

    const fetchStatistics = async () => {
      try {
        setLoading(true);
        const url = `${API_BASE}/runs/${runId}/statistics?procedure=${encodeURIComponent(procedure)}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        setStatistics(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch statistics');
        setStatistics(null);
      } finally {
        setLoading(false);
      }
    };

    fetchStatistics();
  }, [runId, procedure]);

  return { statistics, loading, error };
}

/**
 * Hook for managing breakpoints.
 */
export function useBreakpoints(procedureName: string | null) {
  const [breakpoints, setBreakpoints] = useState<Breakpoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBreakpoints = useCallback(async () => {
    if (!procedureName) {
      setBreakpoints([]);
      return;
    }

    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/breakpoints/${procedureName}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data = await response.json();
      setBreakpoints(data.breakpoints || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch breakpoints');
      setBreakpoints([]);
    } finally {
      setLoading(false);
    }
  }, [procedureName]);

  const setBreakpoint = useCallback(
    async (line: number, condition?: string) => {
      if (!procedureName) return;

      try {
        const response = await fetch(`${API_BASE}/breakpoints/${procedureName}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ line, condition }),
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        // Refresh breakpoints list
        await fetchBreakpoints();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to set breakpoint');
        throw err;
      }
    },
    [procedureName, fetchBreakpoints]
  );

  useEffect(() => {
    fetchBreakpoints();
  }, [fetchBreakpoints]);

  return {
    breakpoints,
    loading,
    error,
    setBreakpoint,
    refetch: fetchBreakpoints,
  };
}

/**
 * Hook for comparing two runs.
 */
export function useRunComparison(runId1: string | null, runId2: string | null) {
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId1 || !runId2) {
      setComparison(null);
      return;
    }

    const compareRuns = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${API_BASE}/compare`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run_id1: runId1, run_id2: runId2 }),
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        setComparison(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to compare runs');
        setComparison(null);
      } finally {
        setLoading(false);
      }
    };

    compareRuns();
  }, [runId1, runId2]);

  return { comparison, loading, error };
}
