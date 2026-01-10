import React from 'react';
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  Timer,
  DollarSign,
  Bot,
  RotateCw,
  Wrench,
} from 'lucide-react';
import { TestScenarioCompletedEvent } from '@/types/events';

type ScenarioStatus = 'pending' | 'running' | 'passed' | 'failed';

interface CollapsibleTestScenarioProps {
  scenarioName: string;
  status: ScenarioStatus;
  scenarioIndex: number;
  totalScenarios: number;
  result?: TestScenarioCompletedEvent;
  isExpanded: boolean;
  onToggle: () => void;
}

export const CollapsibleTestScenario: React.FC<CollapsibleTestScenarioProps> = ({
  scenarioName,
  status,
  scenarioIndex,
  totalScenarios,
  result,
  isExpanded,
  onToggle,
}) => {
  // Status icons
  const statusIcon = {
    pending: <Clock className="h-4 w-4 text-muted-foreground" />,
    running: <Loader2 className="h-4 w-4 animate-spin text-blue-500" />,
    passed: <CheckCircle className="h-4 w-4 text-green-500" />,
    failed: <XCircle className="h-4 w-4 text-red-500" />,
  }[status];

  // Background color based on status
  const bgClass = {
    pending: '',
    running: 'bg-blue-500/5',
    passed: '',
    failed: 'bg-red-500/5',
  }[status];

  return (
    <div className={`border-b border-border/30 ${bgClass}`}>
      {/* Header row */}
      <button
        onClick={onToggle}
        className="w-full px-3 py-2 flex items-center justify-between hover:bg-muted/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          {statusIcon}
          <span className="text-sm font-medium">{scenarioName}</span>
          <span className="text-xs text-muted-foreground">
            ({scenarioIndex + 1}/{totalScenarios})
          </span>
        </div>
        <div className="flex items-center gap-3">
          {/* Show duration when available */}
          {result && result.duration != null && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Timer className="h-3 w-3" />
              {(result.duration * 1000).toFixed(0)}ms
            </span>
          )}
        </div>
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-3 pb-3 border-t border-border/20">
          {/* Running state */}
          {status === 'running' && (
            <div className="py-4 text-sm text-muted-foreground text-center">
              Running scenario...
            </div>
          )}

          {/* Pending state */}
          {status === 'pending' && (
            <div className="py-4 text-sm text-muted-foreground text-center">
              Waiting to run...
            </div>
          )}

          {/* Completed state - show details */}
          {result && (status === 'passed' || status === 'failed') && (
            <div className="pt-2">
              {/* Metrics row */}
              {((result.total_cost != null && result.total_cost > 0) ||
                (result.llm_calls != null && result.llm_calls > 0) ||
                (result.iterations != null && result.iterations > 0) ||
                (result.tools_used != null && result.tools_used.length > 0)) && (
                <div className="flex items-center gap-3 mb-2 text-xs text-muted-foreground flex-wrap">
                  {result.total_cost != null && result.total_cost > 0 && (
                    <span className="flex items-center gap-1">
                      <DollarSign className="h-3 w-3" />
                      ${result.total_cost.toFixed(6)}
                    </span>
                  )}
                  {result.llm_calls != null && result.llm_calls > 0 && (
                    <span className="flex items-center gap-1">
                      <Bot className="h-3 w-3" />
                      {result.llm_calls} calls
                    </span>
                  )}
                  {result.iterations != null && result.iterations > 0 && (
                    <span className="flex items-center gap-1">
                      <RotateCw className="h-3 w-3" />
                      {result.iterations} iterations
                    </span>
                  )}
                  {result.tools_used != null && result.tools_used.length > 0 && (
                    <span className="flex items-center gap-1">
                      <Wrench className="h-3 w-3" />
                      {result.tools_used.length} tools
                    </span>
                  )}
                </div>
              )}

              {/* Steps */}
              {result.steps && result.steps.length > 0 && (
                <div className="space-y-1">
                  {result.steps.map((step, index) => {
                    const isFailed = step.status === 'failed' || step.status === 'error';
                    const isUndefined = step.status === 'undefined';
                    const isSkipped = step.status === 'skipped';
                    const isPassed = step.status === 'passed';

                    return (
                      <div
                        key={index}
                        className={`text-xs ${
                          isFailed || isUndefined
                            ? 'text-red-400'
                            : isSkipped
                            ? 'text-muted-foreground/50'
                            : 'text-muted-foreground'
                        }`}
                      >
                        <span
                          className={`mr-1 ${
                            isFailed
                              ? 'text-red-400'
                              : isUndefined
                              ? 'text-yellow-400'
                              : isSkipped
                              ? 'text-muted-foreground'
                              : isPassed
                              ? 'text-green-400'
                              : 'text-muted-foreground'
                          }`}
                        >
                          {isFailed ? '✗' : isUndefined ? '?' : isSkipped ? '○' : isPassed ? '✓' : '•'}
                        </span>
                        <span className="font-medium">{step.keyword}</span> {step.text}
                        {step.error_message && (
                          <div className="ml-4 mt-1 text-xs text-red-400/80 whitespace-pre-wrap bg-red-500/10 p-2 rounded">
                            {step.error_message}
                          </div>
                        )}
                        {isUndefined && (
                          <div className="ml-4 mt-1 text-xs text-yellow-400/80">
                            Step not implemented
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
