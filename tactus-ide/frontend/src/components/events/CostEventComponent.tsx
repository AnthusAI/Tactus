import React, { useState } from 'react';
import { CostEvent } from '@/types/events';
import { ChevronDown, ChevronRight, DollarSign } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CostEventComponentProps {
  event: CostEvent;
}

export const CostEventComponent: React.FC<CostEventComponentProps> = ({ event }) => {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div className="py-2 px-3 text-sm border-b border-border/50 bg-green-500/5">
      {/* Primary Metrics - Always Visible */}
      <div className="flex items-center gap-2">
        <DollarSign className="h-4 w-4 text-green-500 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-green-600">
              {event.agent_name}:
            </span>
            <span className="font-bold text-green-700">
              ${event.total_cost.toFixed(6)}
            </span>
          </div>
          <div className="text-xs text-muted-foreground flex items-center gap-2 flex-wrap mt-0.5">
            <span>{event.total_tokens.toLocaleString()} tokens</span>
            <span>•</span>
            <span className="truncate max-w-[200px]">{event.model}</span>
            {event.duration_ms && (
              <>
                <span>•</span>
                <span>{(event.duration_ms / 1000).toFixed(2)}s</span>
              </>
            )}
            {event.retry_count > 0 && (
              <>
                <span>•</span>
                <span className="text-yellow-600">
                  {event.retry_count} {event.retry_count === 1 ? 'retry' : 'retries'}
                </span>
              </>
            )}
            {event.cache_hit && (
              <>
                <span>•</span>
                <span className="text-green-600">cache hit</span>
              </>
            )}
          </div>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-muted/50 transition-colors"
          aria-label={expanded ? "Collapse details" : "Expand details"}
        >
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>
      </div>
      
      {/* Detailed Metrics - Collapsible */}
      {expanded && (
        <div className="mt-2 pt-2 border-t border-border/30 space-y-2 text-xs">
          {/* Cost Breakdown */}
          <div className="space-y-1">
            <div className="font-medium text-muted-foreground">Cost Breakdown</div>
            <div className="grid grid-cols-2 gap-2 pl-2">
              <div>
                <span className="text-muted-foreground">Prompt:</span>
                <span className="ml-1 font-mono">${event.prompt_cost.toFixed(6)}</span>
                <span className="ml-1 text-muted-foreground">({event.prompt_tokens.toLocaleString()} tokens)</span>
              </div>
              <div>
                <span className="text-muted-foreground">Completion:</span>
                <span className="ml-1 font-mono">${event.completion_cost.toFixed(6)}</span>
                <span className="ml-1 text-muted-foreground">({event.completion_tokens.toLocaleString()} tokens)</span>
              </div>
            </div>
          </div>
          
          {/* Performance Metrics */}
          {(event.duration_ms || event.latency_ms) && (
            <div className="space-y-1">
              <div className="font-medium text-muted-foreground">Performance</div>
              <div className="grid grid-cols-2 gap-2 pl-2">
                {event.duration_ms && (
                  <div>
                    <span className="text-muted-foreground">Duration:</span>
                    <span className="ml-1">{event.duration_ms.toFixed(0)}ms</span>
                  </div>
                )}
                {event.latency_ms && (
                  <div>
                    <span className="text-muted-foreground">Latency:</span>
                    <span className="ml-1">{event.latency_ms.toFixed(0)}ms</span>
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Retry Information */}
          {event.retry_count > 0 && (
            <div className="space-y-1">
              <div className="font-medium text-yellow-600">Validation Retries</div>
              <div className="pl-2">
                <div>
                  <span className="text-muted-foreground">Retry count:</span>
                  <span className="ml-1 text-yellow-600">{event.retry_count}</span>
                </div>
                {event.validation_errors.length > 0 && (
                  <div className="mt-1 space-y-0.5">
                    <div className="text-muted-foreground">Errors:</div>
                    {event.validation_errors.map((err, i) => (
                      <div key={i} className="text-yellow-600 text-xs pl-2">• {err}</div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Cache Information */}
          {event.cache_hit && (
            <div className="space-y-1">
              <div className="font-medium text-green-600">Cache</div>
              <div className="pl-2">
                <div>
                  <span className="text-muted-foreground">Status:</span>
                  <span className="ml-1 text-green-600">Hit</span>
                </div>
                {event.cache_tokens && (
                  <div>
                    <span className="text-muted-foreground">Cached tokens:</span>
                    <span className="ml-1">{event.cache_tokens.toLocaleString()}</span>
                  </div>
                )}
                {event.cache_cost && (
                  <div>
                    <span className="text-muted-foreground">Saved:</span>
                    <span className="ml-1 text-green-600">${event.cache_cost.toFixed(6)}</span>
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Message Counts */}
          <div className="space-y-1">
            <div className="font-medium text-muted-foreground">Messages</div>
            <div className="grid grid-cols-2 gap-2 pl-2">
              <div>
                <span className="text-muted-foreground">Total:</span>
                <span className="ml-1">{event.message_count}</span>
              </div>
              <div>
                <span className="text-muted-foreground">New:</span>
                <span className="ml-1">{event.new_message_count}</span>
              </div>
            </div>
          </div>
          
          {/* Model Settings */}
          {(event.temperature !== null && event.temperature !== undefined || event.max_tokens) && (
            <div className="space-y-1">
              <div className="font-medium text-muted-foreground">Model Settings</div>
              <div className="grid grid-cols-2 gap-2 pl-2">
                {event.temperature !== null && event.temperature !== undefined && (
                  <div>
                    <span className="text-muted-foreground">Temperature:</span>
                    <span className="ml-1">{event.temperature}</span>
                  </div>
                )}
                {event.max_tokens && (
                  <div>
                    <span className="text-muted-foreground">Max tokens:</span>
                    <span className="ml-1">{event.max_tokens.toLocaleString()}</span>
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Request Metadata */}
          {(event.request_id || event.model_version || event.provider) && (
            <div className="space-y-1">
              <div className="font-medium text-muted-foreground">Request Metadata</div>
              <div className="pl-2 space-y-0.5">
                {event.provider && (
                  <div>
                    <span className="text-muted-foreground">Provider:</span>
                    <span className="ml-1">{event.provider}</span>
                  </div>
                )}
                {event.model_version && (
                  <div>
                    <span className="text-muted-foreground">Model version:</span>
                    <span className="ml-1 font-mono text-xs">{event.model_version}</span>
                  </div>
                )}
                {event.request_id && (
                  <div>
                    <span className="text-muted-foreground">Request ID:</span>
                    <span className="ml-1 font-mono text-xs break-all">{event.request_id}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
