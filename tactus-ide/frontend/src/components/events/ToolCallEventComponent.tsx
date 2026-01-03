import React from 'react';
import { ToolCallEvent } from '@/types/events';
import { BaseEventComponent } from './BaseEventComponent';
import { Wrench } from 'lucide-react';

interface ToolCallEventComponentProps {
  event: ToolCallEvent;
  isAlternate?: boolean;
}

export const ToolCallEventComponent: React.FC<ToolCallEventComponentProps> = ({ event, isAlternate }) => {
  const formatArgs = (args: Record<string, any>) => {
    const entries = Object.entries(args);
    if (entries.length === 0) return '';
    if (entries.length === 1 && JSON.stringify(args).length < 60) {
      return ` ${JSON.stringify(args)}`;
    }
    return '';
  };

  const formatResult = (result: any) => {
    if (result === null || result === undefined) return '';
    const resultStr = String(result);
    if (resultStr.length < 40) {
      return ` → ${resultStr}`;
    }
    return ` → ${resultStr.slice(0, 37)}...`;
  };

  return (
    <BaseEventComponent isAlternate={isAlternate} className="py-1.5 px-3">
      <div className="flex items-start gap-2 text-sm">
        <Wrench className="h-4 w-4 text-cyan-500 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <span className="font-medium text-foreground">{event.tool_name}</span>
          <span className="text-muted-foreground">{formatArgs(event.tool_args)}</span>
          <span className="text-muted-foreground">{formatResult(event.tool_result)}</span>
          {event.duration_ms && (
            <span className="text-muted-foreground ml-2">({event.duration_ms.toFixed(0)}ms)</span>
          )}
        </div>
      </div>
    </BaseEventComponent>
  );
};
