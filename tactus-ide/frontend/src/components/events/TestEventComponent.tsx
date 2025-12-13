import React from 'react';
import { 
  TestStartedEvent, 
  TestCompletedEvent,
  TestScenarioStartedEvent,
  TestScenarioCompletedEvent 
} from '@/types/events';
import { CheckCircle, XCircle, Clock } from 'lucide-react';

export const TestStartedEventComponent: React.FC<{ event: TestStartedEvent }> = ({ event }) => {
  return (
    <div className="py-2 px-3 border-b border-border/50 bg-blue-500/10">
      <div className="flex items-center gap-2">
        <Clock className="h-4 w-4 text-blue-400" />
        <span className="font-medium text-blue-400">Test Started</span>
      </div>
      <div className="text-sm text-muted-foreground mt-1">
        Running {event.total_scenarios} scenario{event.total_scenarios !== 1 ? 's' : ''}
      </div>
    </div>
  );
};

export const TestScenarioCompletedEventComponent: React.FC<{ event: TestScenarioCompletedEvent }> = ({ event }) => {
  const isPassed = event.status === 'passed';
  const isFailed = event.status === 'failed';
  
  return (
    <div className={`py-1.5 px-3 border-b border-border/50 ${isPassed ? 'bg-green-500/5' : isFailed ? 'bg-red-500/5' : 'bg-muted/30'}`}>
      <div className="flex items-center gap-2">
        {isPassed && <CheckCircle className="h-3.5 w-3.5 text-green-500" />}
        {isFailed && <XCircle className="h-3.5 w-3.5 text-red-500" />}
        <span className="text-sm font-medium">{event.scenario_name}</span>
        <span className="text-xs text-muted-foreground ml-auto">
          {(event.duration * 1000).toFixed(0)}ms
        </span>
        {event.total_cost != null && event.total_cost > 0 && (
          <span className="text-xs text-muted-foreground">
            💰 ${event.total_cost.toFixed(6)}
          </span>
        )}
        {event.llm_calls != null && event.llm_calls > 0 && (
          <span className="text-xs text-muted-foreground">
            🤖 {event.llm_calls}
          </span>
        )}
        {event.iterations != null && event.iterations > 0 && (
          <span className="text-xs text-muted-foreground">
            🔄 {event.iterations}
          </span>
        )}
        {event.tools_used != null && event.tools_used.length > 0 && (
          <span className="text-xs text-muted-foreground">
            🔧 {event.tools_used.length}
          </span>
        )}
      </div>
    </div>
  );
};

export const TestCompletedEventComponent: React.FC<{ event: TestCompletedEvent }> = ({ event }) => {
  const { result } = event;
  const allPassed = result.failed_scenarios === 0;
  
  return (
    <div className={`py-3 px-3 border-b border-border/50 ${allPassed ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
      <div className="flex items-center gap-2 mb-2">
        {allPassed ? (
          <CheckCircle className="h-5 w-5 text-green-500" />
        ) : (
          <XCircle className="h-5 w-5 text-red-500" />
        )}
        <span className="font-semibold">
          {allPassed ? 'All Tests Passed' : 'Tests Failed'}
        </span>
      </div>
      
      <div className="grid grid-cols-3 gap-2 text-sm">
        <div>
          <div className="text-muted-foreground text-xs">Total</div>
          <div className="font-medium">{result.total_scenarios}</div>
        </div>
        <div>
          <div className="text-muted-foreground text-xs">Passed</div>
          <div className="font-medium text-green-500">{result.passed_scenarios}</div>
        </div>
        <div>
          <div className="text-muted-foreground text-xs">Failed</div>
          <div className="font-medium text-red-500">{result.failed_scenarios}</div>
        </div>
      </div>
      
      {/* Execution Metrics Summary */}
        {((result.total_cost != null && result.total_cost > 0) || 
         (result.total_llm_calls != null && result.total_llm_calls > 0)) && (
            <div className="mt-2 pt-2 border-t border-border/30 text-sm">
              <div className="text-muted-foreground text-xs mb-1">Execution Metrics</div>
              {result.total_cost != null && result.total_cost > 0 && (
                <div className="font-medium">
                  💰 ${result.total_cost.toFixed(6)} ({result.total_tokens.toLocaleString()} tokens)
                </div>
              )}
              {result.total_llm_calls != null && result.total_llm_calls > 0 && (
                <div className="font-medium">
                  🤖 {result.total_llm_calls} LLM calls
                </div>
              )}
              {result.total_iterations != null && result.total_iterations > 0 && (
                <div className="font-medium">
                  🔄 {result.total_iterations} iterations
                </div>
              )}
              {result.unique_tools_used != null && result.unique_tools_used.length > 0 && (
                <div className="font-medium">
                  🔧 {result.unique_tools_used.join(', ')}
                </div>
              )}
            </div>
        )}
      
      {/* Show failed/error scenarios with details */}
      {result.features.map((feature, fi) => (
        <div key={fi} className="mt-3">
          {feature.scenarios.filter(s => s.status === 'failed' || s.status === 'error').map((scenario, si) => (
            <div key={si} className="mt-2 p-2 bg-background/50 rounded text-xs">
              <div className="font-medium text-red-400 mb-1">
                {scenario.name}
                <span className="ml-2 text-xs text-red-300">({scenario.status})</span>
              </div>
              {/* Show all steps with their status */}
              {scenario.steps.map((step, sti) => {
                const isFailed = step.status === 'failed' || step.status === 'error';
                const isUndefined = step.status === 'undefined';
                const isSkipped = step.status === 'skipped';
                
                return (
                  <div key={sti} className={`ml-2 ${isFailed || isUndefined ? 'text-red-300' : isSkipped ? 'text-muted-foreground/50' : 'text-muted-foreground'}`}>
                    <span className={isFailed ? 'text-red-400' : isUndefined ? 'text-yellow-400' : isSkipped ? 'text-gray-500' : 'text-green-400'}>
                      {isFailed ? '✗' : isUndefined ? '?' : isSkipped ? '○' : '✓'}
                    </span> {step.keyword} {step.text}
                    {step.error_message && (
                      <div className="ml-4 text-xs text-red-400/80 mt-0.5 whitespace-pre-wrap">
                        {step.error_message}
                      </div>
                    )}
                    {isUndefined && (
                      <div className="ml-4 text-xs text-yellow-400/80 mt-0.5">
                        Step not implemented
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};
