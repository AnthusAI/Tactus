import React from 'react';
import { ExecutionSummaryEvent } from '@/types/events';
import { CheckCircle2, Layers, Wrench } from 'lucide-react';

interface ExecutionSummaryEventComponentProps {
  event: ExecutionSummaryEvent;
}

export const ExecutionSummaryEventComponent: React.FC<ExecutionSummaryEventComponentProps> = ({ event }) => {
  return (
    <div className="py-3 px-4 border-b border-border/50 bg-muted/30">
      <div className="flex items-start gap-3">
        <CheckCircle2 className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
        <div className="flex-1 space-y-3">
          <div className="font-medium text-sm">Execution Summary</div>
          
          {/* Metrics */}
          <div className="flex gap-4 text-xs text-muted-foreground">
            <div>
              <span className="font-medium">Iterations:</span> {event.iterations}
            </div>
            {event.tools_used.length > 0 && (
              <div className="flex items-center gap-1">
                <Wrench className="w-3 h-3" />
                <span className="font-medium">Tools:</span> {event.tools_used.join(', ')}
              </div>
            )}
          </div>
          
          {/* Final State */}
          {Object.keys(event.final_state).length > 0 && (
            <div className="space-y-1">
              <div className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                <Layers className="w-3 h-3" />
                Final State
              </div>
              <div className="bg-background rounded p-2 font-mono text-xs">
                <pre className="whitespace-pre-wrap">{JSON.stringify(event.final_state, null, 2)}</pre>
              </div>
            </div>
          )}
          
          {/* Result */}
          <div className="space-y-1">
            <div className="text-xs font-medium text-muted-foreground">Result</div>
            <div className="bg-background rounded p-2 font-mono text-xs">
              <pre className="whitespace-pre-wrap">{JSON.stringify(event.result, null, 2)}</pre>
            </div>
          </div>
          
          <div className="text-xs text-muted-foreground">
            {new Date(event.timestamp).toLocaleTimeString()}
          </div>
        </div>
      </div>
    </div>
  );
};



