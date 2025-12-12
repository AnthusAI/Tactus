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
      
      {/* Show failed scenarios with details */}
      {result.features.map((feature, fi) => (
        <div key={fi} className="mt-3">
          {feature.scenarios.filter(s => s.status === 'failed').map((scenario, si) => (
            <div key={si} className="mt-2 p-2 bg-background/50 rounded text-xs">
              <div className="font-medium text-red-400 mb-1">{scenario.name}</div>
              {scenario.steps.filter(step => step.status === 'failed').map((step, sti) => (
                <div key={sti} className="ml-2 text-muted-foreground">
                  <span className="text-red-400">✗</span> {step.keyword} {step.text}
                  {step.error_message && (
                    <div className="ml-4 text-xs text-red-400/80 mt-0.5">
                      {step.error_message}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};
