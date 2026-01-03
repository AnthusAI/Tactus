/**
 * Detailed view of a selected checkpoint.
 */

import React, { useState } from 'react';
import { ArrowUpRight } from 'lucide-react';
import type { CheckpointEntry } from '../../types/tracing';
import { Button } from '../ui/button';

interface CheckpointDetailsProps {
  checkpoint: CheckpointEntry;
  onJumpToSource?: (filePath: string, lineNumber: number) => void;
}

export const CheckpointDetails: React.FC<CheckpointDetailsProps> = ({ checkpoint, onJumpToSource }) => {
  const [activeTab, setActiveTab] = useState<'result' | 'state' | 'context'>('result');

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const renderJSON = (data: any, depth = 0) => {
    if (data === null || data === undefined) {
      return <span className="text-gray-500">null</span>;
    }

    if (typeof data === 'string') {
      return <span className="text-green-600 dark:text-green-400">"{data}"</span>;
    }

    if (typeof data === 'number' || typeof data === 'boolean') {
      return <span className="text-blue-600 dark:text-blue-400">{String(data)}</span>;
    }

    if (Array.isArray(data)) {
      if (data.length === 0) return <span className="text-gray-500">[]</span>;
      return (
        <div className="ml-4">
          {data.map((item, idx) => (
            <div key={idx}>
              <span className="text-gray-500">{idx}:</span> {renderJSON(item, depth + 1)}
            </div>
          ))}
        </div>
      );
    }

    if (typeof data === 'object') {
      const entries = Object.entries(data);
      if (entries.length === 0) return <span className="text-gray-500">{'{}'}</span>;
      return (
        <div className="ml-4">
          {entries.map(([key, value]) => (
            <div key={key} className="mb-1">
              <span className="text-purple-600 dark:text-purple-400">{key}:</span>{' '}
              {renderJSON(value, depth + 1)}
            </div>
          ))}
        </div>
      );
    }

    return <span>{String(data)}</span>;
  };

  return (
    <div className="checkpoint-details flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Checkpoint #{checkpoint.position}
          </h3>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {formatTimestamp(checkpoint.timestamp)}
          </span>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded">
            {checkpoint.type}
          </span>
          {checkpoint.duration_ms && (
            <span className="text-gray-600 dark:text-gray-400">
              Duration: {checkpoint.duration_ms.toFixed(2)}ms
            </span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 dark:border-gray-700">
        <button
          onClick={() => setActiveTab('result')}
          className={`px-4 py-2 text-sm font-medium ${
            activeTab === 'result'
              ? 'border-b-2 border-blue-500 text-blue-600 dark:text-blue-400'
              : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
          }`}
        >
          Result
        </button>
        <button
          onClick={() => setActiveTab('state')}
          className={`px-4 py-2 text-sm font-medium ${
            activeTab === 'state'
              ? 'border-b-2 border-blue-500 text-blue-600 dark:text-blue-400'
              : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
          }`}
        >
          State
        </button>
        <button
          onClick={() => setActiveTab('context')}
          className={`px-4 py-2 text-sm font-medium ${
            activeTab === 'context'
              ? 'border-b-2 border-blue-500 text-blue-600 dark:text-blue-400'
              : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
          }`}
        >
          Source
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'result' && (
          <div className="font-mono text-sm">
            {renderJSON(checkpoint.result)}
          </div>
        )}

        {activeTab === 'state' && (
          <div className="font-mono text-sm">
            {checkpoint.captured_vars ? (
              renderJSON(checkpoint.captured_vars)
            ) : (
              <div className="text-gray-500 dark:text-gray-400">
                No state captured at this checkpoint
              </div>
            )}
          </div>
        )}

        {activeTab === 'context' && (
          <div>
            {checkpoint.source_location ? (
              <>
                <div className="mb-4">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                        Location
                      </div>
                      <div className="font-mono text-sm text-gray-900 dark:text-gray-100 break-all">
                        {checkpoint.source_location.file}:{checkpoint.source_location.line}
                      </div>
                      {checkpoint.source_location.function && (
                        <div className="font-mono text-sm text-gray-600 dark:text-gray-400">
                          in {checkpoint.source_location.function}()
                        </div>
                      )}
                    </div>
                  </div>
                  {onJumpToSource && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        console.log('Jump to source clicked:', {
                          file: checkpoint.source_location!.file,
                          line: checkpoint.source_location!.line
                        });
                        onJumpToSource(
                          checkpoint.source_location!.file,
                          checkpoint.source_location!.line
                        );
                      }}
                      className="w-full"
                    >
                      <ArrowUpRight className="h-4 w-4 mr-1" />
                      Jump to Source (Line {checkpoint.source_location.line})
                    </Button>
                  )}
                </div>

                {checkpoint.source_location.code_context && (
                  <div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                      Code Context (Line {checkpoint.source_location.line})
                    </div>
                    <pre className="bg-gray-50 dark:bg-gray-800 p-3 rounded text-xs overflow-x-auto max-w-full">
                      <code className="whitespace-pre">{checkpoint.source_location.code_context.split('\n').map((line, idx, arr) => {
                        // Find the middle line (the checkpoint line)
                        const middleIdx = Math.floor(arr.length / 2);
                        const isCheckpointLine = idx === middleIdx;
                        return (
                          <div
                            key={idx}
                            className={isCheckpointLine ? 'bg-yellow-200 dark:bg-yellow-900/50 -mx-3 px-3' : ''}
                          >
                            {line}
                          </div>
                        );
                      })}</code>
                    </pre>
                  </div>
                )}
              </>
            ) : (
              <div className="text-gray-500 dark:text-gray-400">
                No source location available for this checkpoint
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
