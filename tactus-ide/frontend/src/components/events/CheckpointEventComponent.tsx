import React, { useState } from 'react';
import { CheckpointCreatedEvent } from '@/types/events';
import { BaseEventComponent } from './BaseEventComponent';
import { Pin, ChevronDown, ChevronRight, ArrowUpRight } from 'lucide-react';
import { CheckpointDetails } from '../debugger/CheckpointDetails';
import { Timestamp } from '../Timestamp';
import type { CheckpointEntry } from '@/types/tracing';

interface CheckpointEventComponentProps {
  event: CheckpointCreatedEvent;
  isAlternate?: boolean;
  onJumpToSource?: (filePath: string, lineNumber: number) => void;
}

export const CheckpointEventComponent: React.FC<CheckpointEventComponentProps> = ({ event, isAlternate, onJumpToSource }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const formatType = (type: string) => {
    return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  const formatLocation = (location?: { file: string; line: number }) => {
    if (!location) return '';
    const filename = location.file.split('/').pop();
    return `${filename}:${location.line}`;
  };

  // Convert CheckpointCreatedEvent to CheckpointEntry format for CheckpointDetails
  // Note: CheckpointCreatedEvent is a lightweight event without result/captured_vars
  const checkpointEntry: CheckpointEntry = {
    position: event.checkpoint_position,
    type: event.checkpoint_type,
    timestamp: event.timestamp,
    result: undefined as any, // Not available in the event
    captured_vars: undefined,
    source_location: event.source_location,
    duration_ms: event.duration_ms,
  };

  return (
    <BaseEventComponent isAlternate={isAlternate} className="py-2 px-3 text-sm">
      <div className="flex items-start gap-2">
        <Pin className="h-5 w-5 text-muted-foreground flex-shrink-0 stroke-[2.5]" />
        <div className="flex-1 min-w-0">
          {/* Header row: checkpoint info, jump button, timestamp */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1 min-w-0">
              <span className="text-foreground">Checkpoint</span>
              <span className="text-muted-foreground">•</span>
              <span className="text-muted-foreground">{formatType(event.checkpoint_type)}</span>
            </div>
            <Timestamp timestamp={event.timestamp} />
          </div>

          {/* Second line: source location with jump button and expand/collapse button */}
          {event.source_location && (
            <div className="flex items-center justify-between mt-0.5">
              <div className="flex items-center gap-1">
                <span className="text-xs text-muted-foreground">
                  {formatLocation(event.source_location)}
                </span>
                {onJumpToSource && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onJumpToSource(event.source_location!.file, event.source_location!.line);
                    }}
                    className="p-0.5 hover:bg-muted/50 rounded text-muted-foreground hover:text-foreground transition-colors flex-shrink-0"
                    title={`Jump to ${formatLocation(event.source_location)}`}
                  >
                    <ArrowUpRight className="h-3 w-3" />
                  </button>
                )}
              </div>
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="text-muted-foreground hover:text-foreground p-0.5 rounded hover:bg-muted/50 transition-colors flex-shrink-0"
                aria-label={isExpanded ? "Collapse details" : "Expand details"}
              >
                {isExpanded ? <ChevronDown className="h-3 w-3 stroke-[2]" /> : <ChevronRight className="h-3 w-3 stroke-[2]" />}
              </button>
            </div>
          )}

          {/* Fallback expand button if no source location */}
          {!event.source_location && (
            <div className="flex justify-end mt-0.5">
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="text-muted-foreground hover:text-foreground p-0.5 rounded hover:bg-muted/50 transition-colors flex-shrink-0"
                aria-label={isExpanded ? "Collapse details" : "Expand details"}
              >
                {isExpanded ? <ChevronDown className="h-3 w-3 stroke-[2]" /> : <ChevronRight className="h-3 w-3 stroke-[2]" />}
              </button>
            </div>
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="ml-6 mt-2 border-l-2 border-muted-foreground/30 pl-3">
          <CheckpointDetails checkpoint={checkpointEntry} onJumpToSource={onJumpToSource} />
        </div>
      )}
    </BaseEventComponent>
  );
};
