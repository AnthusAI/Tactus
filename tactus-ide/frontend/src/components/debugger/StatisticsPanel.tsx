/**
 * Display run statistics and metrics.
 */

import React from 'react';
import { useRunStatistics } from '../../hooks/useTracing';

interface StatisticsPanelProps {
  runId: string;
  procedure?: string;
}

export const StatisticsPanel: React.FC<StatisticsPanelProps> = ({ runId, procedure }) => {
  const { statistics, loading, error } = useRunStatistics(runId, procedure);

  if (loading) {
    return (
      <div className="statistics-panel p-4">
        <div className="text-sm text-gray-500 dark:text-gray-400">Loading statistics...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="statistics-panel p-4">
        <div className="text-sm text-red-500">Error: {error}</div>
      </div>
    );
  }

  if (!statistics) {
    return null;
  }

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const checkpointTypes = Object.entries(statistics.checkpoints_by_type || {}).sort(
    ([, a], [, b]) => (b as number) - (a as number)
  );

  const maxCount = Math.max(...Object.values(statistics.checkpoints_by_type || {}));

  return (
    <div className="statistics-panel p-4 bg-gray-50 dark:bg-gray-800">
      <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
        Run Statistics
      </h4>

      <div className="space-y-3">
        {/* Summary metrics */}
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-white dark:bg-gray-900 p-2 rounded">
            <div className="text-xs text-gray-500 dark:text-gray-400">Total Checkpoints</div>
            <div className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {statistics.total_checkpoints}
            </div>
          </div>

          <div className="bg-white dark:bg-gray-900 p-2 rounded">
            <div className="text-xs text-gray-500 dark:text-gray-400">Total Duration</div>
            <div className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {formatDuration(statistics.total_duration_ms)}
            </div>
          </div>
        </div>

        {/* Checkpoint types breakdown */}
        {checkpointTypes.length > 0 && (
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
              Checkpoints by Type
            </div>
            <div className="space-y-1">
              {checkpointTypes.map(([type, count]) => {
                const percentage = ((count as number) / maxCount) * 100;
                return (
                  <div key={type} className="flex items-center gap-2">
                    <div className="text-xs text-gray-600 dark:text-gray-400 w-24 truncate">
                      {type}
                    </div>
                    <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-4 overflow-hidden">
                      <div
                        className="bg-blue-500 h-full flex items-center justify-end px-2"
                        style={{ width: `${percentage}%` }}
                      >
                        <span className="text-xs text-white font-medium">{count}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Source location coverage */}
        <div className="bg-white dark:bg-gray-900 p-2 rounded">
          <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
            Source Location Coverage
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <div
                className="bg-green-500 h-full rounded-full"
                style={{
                  width: `${
                    (statistics.has_source_locations / statistics.total_checkpoints) * 100
                  }%`,
                }}
              />
            </div>
            <span className="text-xs text-gray-600 dark:text-gray-400">
              {statistics.has_source_locations}/{statistics.total_checkpoints}
            </span>
          </div>
        </div>

        {/* Status badge */}
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500 dark:text-gray-400">Status:</span>
          <span
            className={`px-2 py-1 rounded ${
              statistics.status === 'COMPLETED'
                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                : statistics.status === 'RUNNING'
                ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                : statistics.status === 'FAILED'
                ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                : 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
            }`}
          >
            {statistics.status}
          </span>
        </div>
      </div>
    </div>
  );
};
