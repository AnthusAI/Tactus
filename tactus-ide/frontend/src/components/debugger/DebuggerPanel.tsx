/**
 * Main debugger panel component for viewing execution traces.
 */

import React, { useState } from 'react';
import { useRun, useRunList } from '../../hooks/useTracing';
import { CheckpointList } from './CheckpointList';
import { CheckpointDetails } from './CheckpointDetails';
import { RunSelector } from './RunSelector';
import { StatisticsPanel } from './StatisticsPanel';
import type { CheckpointEntry } from '../../types/tracing';

interface DebuggerPanelProps {
  initialRunId?: string;
  onClose?: () => void;
}

export const DebuggerPanel: React.FC<DebuggerPanelProps> = ({ initialRunId, onClose }) => {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(initialRunId || null);
  const [selectedPosition, setSelectedPosition] = useState<number | null>(null);

  const { runs, loading: runsLoading } = useRunList({ limit: 50 });
  const { run, loading: runLoading, error: runError } = useRun(selectedRunId);

  const selectedCheckpoint: CheckpointEntry | undefined = run
    ? run.execution_log.find((cp) => cp.position === selectedPosition)
    : undefined;

  const handleRunSelect = (runId: string) => {
    setSelectedRunId(runId);
    setSelectedPosition(null); // Reset checkpoint selection
  };

  const handleCheckpointSelect = (position: number) => {
    setSelectedPosition(position);
  };

  return (
    <div className="debugger-panel flex flex-col h-full bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Execution Debugger
          </h2>
          {run && (
            <span className="text-sm text-gray-600 dark:text-gray-400">
              {run.procedure_name} • {run.execution_log.length} checkpoints
            </span>
          )}
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            aria-label="Close debugger"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Run Selector */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <RunSelector
          runs={runs}
          selectedRunId={selectedRunId}
          onSelect={handleRunSelect}
          loading={runsLoading}
        />
      </div>

      {/* Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Checkpoint List */}
        <div className="w-1/3 border-r border-gray-200 dark:border-gray-700 flex flex-col">
          {runLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-gray-500 dark:text-gray-400">Loading...</div>
            </div>
          ) : runError ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-red-500">{runError}</div>
            </div>
          ) : run ? (
            <>
              <CheckpointList
                checkpoints={run.execution_log}
                selectedPosition={selectedPosition}
                onSelect={handleCheckpointSelect}
              />
              <div className="border-t border-gray-200 dark:border-gray-700">
                <StatisticsPanel runId={run.run_id} />
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-gray-500 dark:text-gray-400">Select a run to view</div>
            </div>
          )}
        </div>

        {/* Right Panel - Checkpoint Details */}
        <div className="flex-1 flex flex-col">
          {selectedCheckpoint ? (
            <CheckpointDetails checkpoint={selectedCheckpoint} />
          ) : run ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-gray-500 dark:text-gray-400">
                Select a checkpoint to view details
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};
