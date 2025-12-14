import React, { useState } from 'react';
import { ExecutionEvent } from '@/types/events';
import { PlayCircle, CheckCircle, XCircle, Clock, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BaseEventComponent } from './BaseEventComponent';
import { Timestamp } from '../Timestamp';

interface ExecutionEventComponentProps {
  event: ExecutionEvent;
  isAlternate?: boolean;
}

const stageConfig = {
  start: {
    icon: PlayCircle,
    label: 'Started',
    color: 'text-foreground',
  },
  complete: {
    icon: CheckCircle,
    label: 'Completed',
    color: 'text-green-500',
    bg: 'bg-green-500/10',
  },
  error: {
    icon: XCircle,
    label: 'Failed',
    color: 'text-red-500',
    bg: 'bg-red-500/10',
  },
  waiting: {
    icon: Clock,
    label: 'Waiting',
    color: 'text-foreground',
  },
};

export const ExecutionEventComponent: React.FC<ExecutionEventComponentProps> = ({ event, isAlternate }) => {
  const [tracebackExpanded, setTracebackExpanded] = useState(false);
  const config = stageConfig[event.lifecycle_stage as keyof typeof stageConfig] || stageConfig.start;
  const Icon = config.icon;

  return (
    <BaseEventComponent isAlternate={isAlternate} className={cn('py-3 px-3 text-sm', config.bg)}>
      <div className="flex items-start gap-2">
        <Icon className={cn('h-5 w-5 flex-shrink-0 stroke-[2]', config.color)} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className={config.color}>{config.label}</span>
            <Timestamp timestamp={event.timestamp} />
          </div>
          {event.exit_code !== undefined && (
            <div className="text-sm text-muted-foreground mt-1">
              Exit code: {event.exit_code}
            </div>
          )}
          {event.details && Object.keys(event.details).length > 0 && (
            <div className="mt-2 text-sm space-y-2">
          {event.details.path && <div className="text-muted-foreground">Path: {event.details.path}</div>}
          {event.details.error && (
            <div className="bg-red-500/10 rounded p-3 border border-red-500/20 space-y-2">
              <div className="text-sm font-medium text-red-500">Error</div>
              {event.details.error_type && (
                <div className="text-xs font-mono text-red-600 dark:text-red-400">
                  {event.details.error_type}
                </div>
              )}
              <div className="text-sm text-foreground whitespace-pre-wrap">{event.details.error}</div>
              {event.details.traceback && (
                <div className="mt-2">
                  <button
                    onClick={() => setTracebackExpanded(!tracebackExpanded)}
                    className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                  >
                    {tracebackExpanded ? (
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
                  {tracebackExpanded && (
                    <pre className="mt-2 text-xs font-mono whitespace-pre-wrap text-muted-foreground bg-background/50 rounded p-2 overflow-x-auto">
                      {event.details.traceback}
                    </pre>
                  )}
                </div>
              )}
            </div>
          )}
          
          {/* Pydantic Evals Results */}
          {event.details.type === 'pydantic_eval' && event.details.cases && (() => {
            // Group cases by task name (remove _runN suffix)
            const taskGroups: Record<string, any[]> = {};
            event.details.cases.forEach((testCase: any) => {
              const taskName = testCase.name.includes('_run') 
                ? testCase.name.substring(0, testCase.name.lastIndexOf('_run'))
                : testCase.name;
              if (!taskGroups[taskName]) {
                taskGroups[taskName] = [];
              }
              taskGroups[taskName].push(testCase);
            });

            return (
              <div className="mt-2 space-y-4">
                <div className="text-foreground">
                  Evaluation Results ({event.details.total_cases} total runs)
                </div>
                
                {Object.entries(taskGroups).map(([taskName, cases]) => {
                  const totalRuns = cases.length;
                  const successfulRuns = cases.filter(c => 
                    Object.values(c.assertions || {}).every((a: any) => a.value === true)
                  ).length;
                  const successRate = (successfulRuns / totalRuns * 100).toFixed(1);
                  const isSuccess = successfulRuns === totalRuns;
                  
                  // Calculate per-evaluator stats
                  const evaluatorStats: Record<string, {passed: number, total: number}> = {};
                  cases.forEach(c => {
                    Object.entries(c.assertions || {}).forEach(([name, assertion]: [string, any]) => {
                      if (!evaluatorStats[name]) {
                        evaluatorStats[name] = {passed: 0, total: 0};
                      }
                      evaluatorStats[name].total++;
                      if (assertion.value) evaluatorStats[name].passed++;
                    });
                  });

                  return (
                    <div key={taskName} className="border rounded-lg p-3 space-y-2">
                      <div className="flex items-center gap-2">
                        {isSuccess ? (
                          <CheckCircle className="h-4 w-4 text-green-500 stroke-[2]" />
                        ) : (
                          <XCircle className="h-4 w-4 text-red-500 stroke-[2]" />
                        )}
                        <span className="text-foreground">{taskName}</span>
                        <span className={cn('ml-auto text-sm', isSuccess ? 'text-green-500' : 'text-red-500')}>
                          {successRate}% ({successfulRuns}/{totalRuns})
                        </span>
                      </div>

                      {/* Evaluator breakdown */}
                      <div className="text-xs space-y-1">
                        <div className="text-muted-foreground">Evaluators:</div>
                        {Object.entries(evaluatorStats).map(([name, stats]) => {
                          const rate = (stats.passed / stats.total * 100).toFixed(0);
                          return (
                            <div key={name} className="ml-2 text-muted-foreground">
                              {name}: {rate}% ({stats.passed}/{stats.total})
                            </div>
                          );
                        })}
                      </div>

                      {/* Show all runs */}
                      <details className="text-xs">
                        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                          All runs ({cases.length})
                        </summary>
                        <div className="mt-2 space-y-2">
                          {cases.map((testCase: any, idx: number) => {
                            const allPassed = Object.values(testCase.assertions || {}).every((a: any) => a.value === true);
                            return (
                  <div key={idx} className={cn('p-2 rounded border', allPassed ? 'bg-green-500/5 border-green-500/20' : 'bg-red-500/5 border-red-500/20')}>
                    <div className="flex items-center gap-2">
                      {allPassed ? (
                        <CheckCircle className="h-4 w-4 text-green-500 stroke-[2]" />
                      ) : (
                        <XCircle className="h-4 w-4 text-red-500 stroke-[2]" />
                      )}
                                  <span className="text-foreground">{testCase.name}</span>
                                  <span className="ml-auto text-muted-foreground">{(testCase.duration * 1000).toFixed(0)}ms</span>
                                </div>
                                <div className="mt-1 text-muted-foreground">
                                  Input: {JSON.stringify(testCase.inputs)}
                                </div>
                                <div className="mt-1 text-muted-foreground break-words">
                                  Output: {JSON.stringify(testCase.output)}
                                </div>
                                {testCase.assertions && Object.keys(testCase.assertions).length > 0 && (
                                  <div className="mt-1 space-y-1">
                                    <div className="text-muted-foreground">Evaluators:</div>
                                    {Object.entries(testCase.assertions).map(([name, result]: [string, any]) => (
                                      <div key={name} className="ml-2">
                                        <div className="flex items-center gap-1">
                                          {result.value ? (
                                            <CheckCircle className="h-3 w-3 text-green-500 stroke-[2]" />
                                          ) : (
                                            <XCircle className="h-3 w-3 text-red-500 stroke-[2]" />
                                          )}
                                          <span className={result.value ? 'text-green-500' : 'text-red-500'}>{name}</span>
                                        </div>
                                        {result.reason && (
                                          <div className="ml-4 text-muted-foreground text-xs break-words">
                                            {result.reason}
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </details>
                    </div>
                  );
                })}
              </div>
            );
          })()}
            </div>
          )}
        </div>
      </div>
    </BaseEventComponent>
  );
};





