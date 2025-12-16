import React, { useState } from 'react';
import { ExecutionSummaryEvent } from '@/types/events';
import { CheckCircle, XCircle, ChevronDown, ChevronRight, Clock, AlertTriangle } from 'lucide-react';
import { BaseEventComponent } from './BaseEventComponent';
import { Timestamp } from '../Timestamp';

interface ExecutionSummaryEventComponentProps {
  event: ExecutionSummaryEvent;
  isAlternate?: boolean;
}

export const ExecutionSummaryEventComponent: React.FC<ExecutionSummaryEventComponentProps> = ({ event, isAlternate }) => {
  const [metricsExpanded, setMetricsExpanded] = useState(false);
  const [stateExpanded, setStateExpanded] = useState(false);
  const [errorExpanded, setErrorExpanded] = useState(true); // Errors expanded by default
  
  const isError = event.exit_code !== 0 && event.exit_code !== undefined;
  
  // Calculate tool counts
  const toolCounts = event.tools_used.reduce((acc, tool) => {
    acc[tool] = (acc[tool] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  
  // Calculate average duration from cost breakdown
  const avgDuration = event.cost_breakdown && event.cost_breakdown.length > 0
    ? event.cost_breakdown.reduce((sum, cost) => sum + (cost.duration_ms || 0), 0) / event.cost_breakdown.length
    : 0;
  
  return (
    <BaseEventComponent isAlternate={isAlternate} className={`py-3 px-4 text-sm ${isError ? 'bg-red-500/5' : 'bg-green-500/5'}`}>
      <div className="flex items-start gap-3">
        {isError ? (
          <XCircle className="h-5 w-5 text-red-500 flex-shrink-0 stroke-[2]" />
        ) : (
          <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0 stroke-[2]" />
        )}
        <div className="flex-1 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-foreground">{isError ? 'Failed' : 'Finished'}</span>
            <Timestamp timestamp={event.timestamp} />
          </div>
          
          {/* Details line - matching CostEvent format */}
          <div className="text-xs text-muted-foreground">
            {event.iterations} {event.iterations === 1 ? 'iteration' : 'iterations'}
            {event.total_cost > 0 && ` • $${event.total_cost.toFixed(6)}`}
            {event.total_tokens > 0 && ` • ${event.total_tokens.toLocaleString()} tokens`}
            {avgDuration > 0 && ` • ${(avgDuration / 1000).toFixed(2)}s`}
            {event.exit_code !== undefined && ` • Exit code: ${event.exit_code}`}
          </div>
          
          {/* Error Information - Show if error exists */}
          {isError && event.error_message && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-red-500">
                <AlertTriangle className="h-4 w-4 stroke-[2]" />
                <span className="font-medium">Error</span>
              </div>
              <div className="bg-red-500/10 rounded p-3 border border-red-500/20">
                <div className="space-y-2">
                  {event.error_type && (
                    <div className="text-xs font-mono text-red-600 dark:text-red-400">
                      {event.error_type}
                    </div>
                  )}
                  <div className="text-sm text-foreground">
                    {event.error_message}
                  </div>
                  {event.traceback && (
                    <div className="mt-2">
                      <button
                        onClick={() => setErrorExpanded(!errorExpanded)}
                        className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                      >
                        {errorExpanded ? (
                          <>
                            <ChevronDown className="h-3 w-3 stroke-[2]" />
                            Hide traceback
                          </>
                        ) : (
                          <>
                            <ChevronRight className="h-3 w-3 stroke-[2]" />
                            Show traceback
                          </>
                        )}
                      </button>
                      {errorExpanded && (
                        <pre className="mt-2 text-xs font-mono whitespace-pre-wrap text-muted-foreground bg-background/50 rounded p-2 overflow-x-auto">
                          {event.traceback}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Result - Always Visible */}
          {event.result !== null && (
            <div className="border rounded bg-background">
              <div className="p-2">
                <span className="text-sm text-foreground">Result</span>
              </div>
              <div className="px-3 pb-3">
                <pre className="text-xs font-mono whitespace-pre-wrap">{JSON.stringify(event.result, null, 2)}</pre>
              </div>
            </div>
          )}

          {/* Collapsible expanded metrics */}
          <div className="border rounded bg-background">
            <button
              onClick={() => setMetricsExpanded(!metricsExpanded)}
              className="w-full flex items-center justify-between p-2 hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-2 text-sm">
                <span className="text-foreground">Usage</span>
              </div>
              {metricsExpanded ? (
                <ChevronDown className="h-4 w-4 stroke-[2]" />
              ) : (
                <ChevronRight className="h-4 w-4 stroke-[2]" />
              )}
            </button>
            
            {metricsExpanded && (
              <div className="px-3 pb-3 space-y-3 text-xs">
                {/* Cost Breakdown */}
                {event.total_cost > 0 && (
                  <div>
                    <div className="text-muted-foreground mb-1">Cost Breakdown</div>
                    <div className="space-y-1 pl-2">
                      <div className="flex justify-between">
                        <span>Total Cost:</span>
                        <span className="font-mono">${event.total_cost.toFixed(6)}</span>
                      </div>
                      {event.cost_breakdown && event.cost_breakdown.length > 0 && (
                        <div className="mt-2 space-y-1">
                          {event.cost_breakdown.map((cost, i) => (
                            <div key={i} className="flex justify-between text-muted-foreground">
                              <span>{cost.agent_name}</span>
                              <span className="font-mono">${cost.total_cost.toFixed(6)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
                
                {/* Token Usage */}
                {event.total_tokens > 0 && (
                  <div>
                    <div className="text-muted-foreground mb-1">Token Usage</div>
                    <div className="space-y-1 pl-2">
                      <div className="flex justify-between">
                        <span>Total Tokens:</span>
                        <span>{event.total_tokens.toLocaleString()}</span>
                      </div>
                      {event.cost_breakdown && event.cost_breakdown.length > 0 && (
                        <div className="mt-2 space-y-1">
                          {event.cost_breakdown.map((cost, i) => (
                            <div key={i} className="flex justify-between text-muted-foreground">
                              <span>{cost.agent_name}:</span>
                              <span>
                                {cost.prompt_tokens.toLocaleString()} + {cost.completion_tokens.toLocaleString()}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
                
                {/* Tool Usage */}
                {Object.keys(toolCounts).length > 0 && (
                  <div>
                    <div className="text-muted-foreground mb-1">Tool Usage</div>
                    <div className="space-y-1 pl-2">
                      {Object.entries(toolCounts).map(([tool, count]) => (
                        <div key={tool} className="flex justify-between">
                          <span>{tool}</span>
                          <span className="text-muted-foreground">×{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Performance */}
                {avgDuration > 0 && (
                  <div>
                    <div className="text-muted-foreground mb-1">Performance</div>
                    <div className="space-y-1 pl-2">
                      <div className="flex justify-between items-center">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3 stroke-[2]" />
                          Average Response Time:
                        </span>
                        <span>{(avgDuration / 1000).toFixed(2)}s</span>
                      </div>
                      {event.cost_breakdown && event.cost_breakdown.length > 1 && (
                        <div className="flex justify-between">
                          <span>Total Requests:</span>
                          <span>{event.cost_breakdown.length}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
          
          {/* Collapsible State Section */}
          {Object.keys(event.final_state).length > 0 && (
            <div className="border rounded bg-background">
              <button
                onClick={() => setStateExpanded(!stateExpanded)}
                className="w-full flex items-center justify-between p-2 hover:bg-muted/50 transition-colors"
              >
              <div className="flex items-center gap-2 text-sm">
                <span className="text-foreground">Final State</span>
                </div>
                {stateExpanded ? (
                  <ChevronDown className="h-4 w-4 stroke-[2]" />
                ) : (
                  <ChevronRight className="h-4 w-4 stroke-[2]" />
                )}
              </button>
              
              {stateExpanded && (
                <div className="px-3 pb-3">
                  <div className="bg-muted/30 rounded p-2 font-mono text-xs">
                    <pre className="whitespace-pre-wrap">{JSON.stringify(event.final_state, null, 2)}</pre>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </BaseEventComponent>
  );
};





