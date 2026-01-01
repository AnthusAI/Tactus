/**
 * Dropdown selector for choosing execution runs.
 */

import React from 'react';
import type { RunListItem } from '../../types/tracing';

interface RunSelectorProps {
  runs: RunListItem[];
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
  loading?: boolean;
}

export const RunSelector: React.FC<RunSelectorProps> = ({
  runs,
  selectedRunId,
  onSelect,
  loading = false,
}) => {
  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'RUNNING':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'PAUSED':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
      case 'FAILED':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
    }
  };

  const selectedRun = runs.find((r) => r.run_id === selectedRunId);

  return (
    <div className="run-selector">
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
        Select Run
      </label>

      {loading ? (
        <div className="text-sm text-gray-500 dark:text-gray-400">Loading runs...</div>
      ) : runs.length === 0 ? (
        <div className="text-sm text-gray-500 dark:text-gray-400">No runs available</div>
      ) : (
        <select
          value={selectedRunId || ''}
          onChange={(e) => onSelect(e.target.value)}
          className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-900 dark:text-gray-100"
        >
          <option value="" className="bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100">
            Select a run...
          </option>
          {runs.map((run) => (
            <option
              key={run.run_id}
              value={run.run_id}
              className="bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            >
              {run.procedure_name} - {formatTimestamp(run.start_time)} ({run.checkpoint_count}{' '}
              checkpoints)
            </option>
          ))}
        </select>
      )}

      {/* Selected run details */}
      {selectedRun && (
        <div className="mt-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-md">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {selectedRun.procedure_name}
            </span>
            <span className={`text-xs px-2 py-1 rounded ${getStatusColor(selectedRun.status)}`}>
              {selectedRun.status}
            </span>
          </div>

          <div className="space-y-1 text-xs text-gray-600 dark:text-gray-400">
            <div className="flex items-center justify-between">
              <span>Run ID:</span>
              <span className="font-mono">{selectedRun.run_id.slice(0, 8)}...</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Started:</span>
              <span>{formatTimestamp(selectedRun.start_time)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Checkpoints:</span>
              <span>{selectedRun.checkpoint_count}</span>
            </div>
            {selectedRun.end_time && (
              <div className="flex items-center justify-between">
                <span>Ended:</span>
                <span>{formatTimestamp(selectedRun.end_time)}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
