import React, { useState } from 'react';
import { ExecutionSummaryEvent } from '@/types/events';
import { CheckCircle2, Layers, Wrench, DollarSign, ChevronDown, ChevronRight } from 'lucide-react';

interface ExecutionSummaryEventComponentProps {
  event: ExecutionSummaryEvent;
}

export const ExecutionSummaryEventComponent: React.FC<ExecutionSummaryEventComponentProps> = ({ event }) => {
  const [costExpanded, setCostExpanded] = useState(false);
  
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
          
          {/* Cost Summary */}
          {event.total_cost > 0 && (
            <div className="p-3 bg-green-500/10 rounded border border-green-500/20">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <DollarSign className="w-4 h-4 text-green-600" />
                  <span className="font-semibold text-green-600">Cost Summary</span>
                </div>
                {event.cost_breakdown && event.cost_breakdown.length > 0 && (
                  <button
                    onClick={() => setCostExpanded(!costExpanded)}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    {costExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </button>
                )}
              </div>
              <div className="text-sm mt-2 space-y-1">
                <div className="flex justify-between">
                  <span>Total Cost:</span>
                  <span className="font-bold text-green-700">${event.total_cost.toFixed(6)}</span>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Total Tokens:</span>
                  <span>{event.total_tokens.toLocaleString()}</span>
                </div>
              </div>
              
              {/* Per-call breakdown - collapsible */}
              {costExpanded && event.cost_breakdown && event.cost_breakdown.length > 0 && (
                <div className="mt-3 pt-3 border-t border-green-500/20">
                  <div className="text-xs font-medium mb-2">Per-call breakdown:</div>
                  <div className="space-y-1.5">
                    {event.cost_breakdown.map((cost, i) => (
                      <div key={i} className="text-xs flex justify-between items-center">
                        <div className="flex-1">
                          <span className="font-medium">{cost.agent_name}</span>
                          <span className="text-muted-foreground ml-2">
                            {cost.total_tokens.toLocaleString()} tokens
                          </span>
                          {cost.duration_ms && (
                            <span className="text-muted-foreground ml-2">
                              {(cost.duration_ms / 1000).toFixed(2)}s
                            </span>
                          )}
                        </div>
                        <span className="font-mono">${cost.total_cost.toFixed(6)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          
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



