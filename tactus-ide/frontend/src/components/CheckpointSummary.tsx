/**
 * Checkpoint Summary - Displays checkpoint metrics and optional expandable list.
 * Used in Results tab to show checkpoint information within each run.
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Circle, ArrowUpRight } from 'lucide-react';
import type { CheckpointEntry } from '../types/tracing';
import { CheckpointDetails } from './debugger/CheckpointDetails';

interface CheckpointSummaryProps {
  checkpoints: CheckpointEntry[];
  onJumpToSource?: (filePath: string, lineNumber: number) => void;
}

export const CheckpointSummary: React.FC<CheckpointSummaryProps> = ({ checkpoints, onJumpToSource }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [expandedPosition, setExpandedPosition] = useState<number | null>(null);

  if (!checkpoints || checkpoints.length === 0) {
    return null;
  }

  // Calculate metrics
  const totalCheckpoints = checkpoints.length;
  const checkpointsByType = checkpoints.reduce((acc, cp) => {
    acc[cp.type] = (acc[cp.type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const totalDurationMs = checkpoints.reduce((sum, cp) => {
    return sum + (cp.duration_ms || 0);
  }, 0);

  const avgDurationMs = totalDurationMs / totalCheckpoints;

  // Find first checkpoint with source location for the Jump button
  const firstCheckpointWithSource = checkpoints.find(cp => cp.source_location);

  // Format type display (e.g., "agent_turn" -> "Agent Turn")
  const formatType = (type: string) => {
    return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  return (
    <div className="border-t border-border/30 bg-muted/20">
      {/* Summary Header */}
      <div className="flex items-center">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex-1 px-3 py-2 flex items-center justify-between hover:bg-muted/30 transition-colors text-left"
        >
          <div className="flex items-center gap-2">
            <Circle className="h-3 w-3 text-yellow-500 fill-yellow-500" />
            <span className="text-xs font-medium text-muted-foreground">
              Checkpoints
            </span>
            <span className="text-xs text-muted-foreground">
              {totalCheckpoints} total
            </span>
            {totalDurationMs > 0 && (
              <>
                <span className="text-xs text-muted-foreground">•</span>
                <span className="text-xs text-muted-foreground">
                  {avgDurationMs.toFixed(0)}ms avg
                </span>
              </>
            )}
          </div>
          {isExpanded ? (
            <ChevronUp className="h-3 w-3 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          )}
        </button>
        {/* Jump to Source button visible even when collapsed */}
        {!isExpanded && firstCheckpointWithSource && onJumpToSource && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onJumpToSource(
                firstCheckpointWithSource.source_location!.file,
                firstCheckpointWithSource.source_location!.line
              );
            }}
            className="px-2 py-2 hover:bg-muted/30 transition-colors border-l border-border/30"
            title={`Jump to ${firstCheckpointWithSource.source_location!.file.split('/').pop()}:${firstCheckpointWithSource.source_location!.line}`}
          >
            <ArrowUpRight className="h-3 w-3 text-muted-foreground hover:text-foreground" />
          </button>
        )}
      </div>

      {/* Expanded Details */}
      {isExpanded && (
        <div className="px-3 pb-3 space-y-2">
          {/* Types Breakdown */}
          <div className="text-xs">
            <div className="text-muted-foreground mb-1">Types:</div>
            <div className="pl-2 space-y-1">
              {Object.entries(checkpointsByType)
                .sort((a, b) => b[1] - a[1]) // Sort by count descending
                .map(([type, count]) => (
                  <div key={type} className="flex items-center justify-between">
                    <span className="text-muted-foreground">{formatType(type)}</span>
                    <span className="text-muted-foreground font-mono">{count}</span>
                  </div>
                ))}
            </div>
          </div>

          {/* Duration Stats */}
          {totalDurationMs > 0 && (
            <div className="text-xs">
              <div className="text-muted-foreground mb-1">Duration:</div>
              <div className="pl-2 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Average</span>
                  <span className="text-muted-foreground font-mono">
                    {avgDurationMs.toFixed(0)}ms
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Total</span>
                  <span className="text-muted-foreground font-mono">
                    {(totalDurationMs / 1000).toFixed(1)}s
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Individual Checkpoints List */}
          <div className="text-xs">
            <div className="text-muted-foreground mb-1">Checkpoints:</div>
            <div className="pl-2 space-y-1 max-h-48 overflow-y-auto">
              {checkpoints.map((checkpoint) => (
                <div key={checkpoint.position}>
                  <div className="flex items-start gap-2 py-1 hover:bg-muted/30 rounded px-1 -ml-1">
                    <div
                      onClick={() => setExpandedPosition(
                        checkpoint.position === expandedPosition ? null : checkpoint.position
                      )}
                      className="flex items-start gap-2 flex-1 cursor-pointer"
                    >
                      <span className="font-mono text-muted-foreground min-w-[2rem]">
                        #{checkpoint.position}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-muted-foreground truncate">
                          {formatType(checkpoint.type)}
                        </div>
                        {checkpoint.source_location && (
                          <div className="text-muted-foreground/70 truncate text-[10px]">
                            {checkpoint.source_location.file.split('/').pop()}:
                            {checkpoint.source_location.line}
                          </div>
                        )}
                      </div>
                      {checkpoint.duration_ms && (
                        <span className="text-muted-foreground font-mono text-[10px] whitespace-nowrap">
                          {checkpoint.duration_ms.toFixed(0)}ms
                        </span>
                      )}
                    </div>
                    {/* Jump to Source button */}
                    {checkpoint.source_location && onJumpToSource && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onJumpToSource(
                            checkpoint.source_location!.file,
                            checkpoint.source_location!.line
                          );
                        }}
                        className="p-1 hover:bg-muted/50 rounded text-muted-foreground hover:text-foreground transition-colors"
                        title={`Jump to line ${checkpoint.source_location.line}`}
                      >
                        <ArrowUpRight className="h-3 w-3" />
                      </button>
                    )}
                  </div>

                  {expandedPosition === checkpoint.position && (
                    <div className="ml-6 mt-2 mb-2 border-l-2 border-yellow-500/30 pl-3">
                      <CheckpointDetails checkpoint={checkpoint} onJumpToSource={onJumpToSource} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
