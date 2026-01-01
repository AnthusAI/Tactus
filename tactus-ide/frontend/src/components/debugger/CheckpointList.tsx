/**
 * Scrollable list of checkpoints with selection.
 */

import React from 'react';
import { Bot, Brain, User, MapPin, Circle } from 'lucide-react';
import type { CheckpointEntry } from '../../types/tracing';

interface CheckpointListProps {
  checkpoints: CheckpointEntry[];
  selectedPosition: number | null;
  onSelect: (position: number) => void;
}

export const CheckpointList: React.FC<CheckpointListProps> = ({
  checkpoints,
  selectedPosition,
  onSelect,
}) => {
  const getCheckpointIcon = (type: string) => {
    const className = "w-4 h-4 flex-shrink-0";
    switch (type) {
      case 'agent_turn':
        return <Bot className={className} />;
      case 'model_predict':
        return <Brain className={className} />;
      case 'human_input':
        return <User className={className} />;
      case 'step':
        return <MapPin className={className} />;
      default:
        return <Circle className={className} />;
    }
  };

  const getCheckpointColor = (type: string) => {
    switch (type) {
      case 'agent_turn':
        return 'border-blue-500';
      case 'model_predict':
        return 'border-purple-500';
      case 'human_input':
        return 'border-green-500';
      case 'step':
        return 'border-yellow-500';
      default:
        return 'border-gray-500';
    }
  };

  return (
    <div className="checkpoint-list flex flex-col h-full overflow-hidden">
      <div className="p-3 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          Checkpoints ({checkpoints.length})
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto">
        {checkpoints.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-500 dark:text-gray-400">
            No checkpoints
          </div>
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {checkpoints.map((checkpoint) => (
              <button
                key={checkpoint.position}
                onClick={() => onSelect(checkpoint.position)}
                className={`w-full text-left p-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors ${
                  selectedPosition === checkpoint.position
                    ? 'bg-blue-50 dark:bg-blue-900/20 border-l-4 ' +
                      getCheckpointColor(checkpoint.type)
                    : 'border-l-4 border-transparent'
                }`}
              >
                <div className="flex items-start gap-2">
                  <div className="mt-0.5">
                    {getCheckpointIcon(checkpoint.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-mono text-gray-500 dark:text-gray-400">
                        #{checkpoint.position}
                      </span>
                      {checkpoint.duration_ms && (
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {checkpoint.duration_ms.toFixed(1)}ms
                        </span>
                      )}
                    </div>
                    <div className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
                      {checkpoint.type.replace(/_/g, ' ')}
                    </div>
                    {checkpoint.source_location && (
                      <div className="text-xs text-gray-600 dark:text-gray-400 truncate">
                        {checkpoint.source_location.file.split('/').pop()}:
                        {checkpoint.source_location.line}
                      </div>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
