import React, { useState } from 'react';
import { CostEvent } from '@/types/events';
import { Coins, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BaseEventComponent } from './BaseEventComponent';
import { Timestamp } from '../Timestamp';

interface CostEventComponentProps {
  event: CostEvent;
  isAlternate?: boolean;
}

export const CostEventComponent: React.FC<CostEventComponentProps> = ({ event, isAlternate }) => {
  const [expanded, setExpanded] = useState(false);
  const hasResponse = event.response_data && Object.keys(event.response_data).length > 0;
  
  return (
    <BaseEventComponent isAlternate={isAlternate} className="py-2 px-3 text-sm">
      <div className="flex items-start gap-2">
        <Coins className="h-5 w-5 text-muted-foreground flex-shrink-0 stroke-[2]" />
        <div className="flex-1 min-w-0">
          {/* Agent name and timestamp - clean alignment */}
          <div className="flex items-center justify-between">
            <span className="text-foreground">{event.agent_name}</span>
            <Timestamp timestamp={event.timestamp} />
          </div>
        </div>
      </div>
      
      {/* Response - First, most prominent */}
      {hasResponse && (
        <div className="mt-2 ml-7 bg-background rounded p-3 border">
          <pre className="text-xs font-mono whitespace-pre-wrap">
            {JSON.stringify(event.response_data, null, 2)}
          </pre>
        </div>
      )}
      
      {/* Cost metrics with expand button - Below response */}
      <div className="mt-2 ml-7 flex items-center justify-between">
        <div className="text-xs text-muted-foreground">
          ${event.total_cost.toFixed(6)} • {event.total_tokens.toLocaleString()} tokens • {event.model} • {event.duration_ms ? `${(event.duration_ms / 1000).toFixed(2)}s` : ''}
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-muted/50 transition-colors"
          aria-label={expanded ? "Collapse details" : "Expand details"}
        >
          {expanded ? <ChevronDown className="h-3 w-3 stroke-[2]" /> : <ChevronRight className="h-3 w-3 stroke-[2]" />}
        </button>
      </div>
      
      {/* Detailed Metrics - Collapsible */}
      {expanded && (
        <div className="mt-2 pt-2 border-t border-border/30 space-y-2 text-xs">
          {/* Cost Breakdown */}
          <div className="space-y-1">
            <div className="text-muted-foreground">Cost Breakdown</div>
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
              <div className="text-muted-foreground">Performance</div>
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
              <div className="text-yellow-600">Validation Retries</div>
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
              <div className="text-green-600">Cache</div>
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
            <div className="text-muted-foreground">Messages</div>
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
              <div className="text-muted-foreground">Model Settings</div>
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
              <div className="text-muted-foreground">Request Metadata</div>
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
    </BaseEventComponent>
  );
};


