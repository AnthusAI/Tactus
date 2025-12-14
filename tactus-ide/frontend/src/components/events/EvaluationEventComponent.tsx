import React from 'react';
import { 
  EvaluationStartedEvent, 
  EvaluationCompletedEvent,
  EvaluationProgressEvent 
} from '@/types/events';
import { BarChart2, TrendingUp, AlertTriangle } from 'lucide-react';
import { BaseEventComponent } from './BaseEventComponent';

export const EvaluationStartedEventComponent: React.FC<{ event: EvaluationStartedEvent; isAlternate?: boolean }> = ({ event, isAlternate }) => {
  return (
    <BaseEventComponent isAlternate={isAlternate} className="py-2 px-3 text-sm">
      <div className="flex items-start gap-2">
        <BarChart2 className="h-5 w-5 text-muted-foreground flex-shrink-0 stroke-[2]" />
        <div className="flex-1 min-w-0">
          <div className="text-foreground">Evaluation Started</div>
          <div className="text-sm text-muted-foreground mt-1">
            Running {event.total_scenarios} scenario{event.total_scenarios !== 1 ? 's' : ''} × {event.runs_per_scenario} times
          </div>
        </div>
      </div>
    </BaseEventComponent>
  );
};

export const EvaluationProgressEventComponent: React.FC<{ event: EvaluationProgressEvent; isAlternate?: boolean }> = ({ event, isAlternate }) => {
  const progress = (event.completed_runs / event.total_runs) * 100;
  
  return (
    <BaseEventComponent isAlternate={isAlternate} className="py-1.5 px-3 text-sm">
      <div className="flex items-center gap-2">
        <div className="text-sm text-foreground">{event.scenario_name}</div>
        <div className="text-xs text-muted-foreground ml-auto">
          {event.completed_runs}/{event.total_runs} runs
        </div>
      </div>
      <div className="mt-1 h-1 bg-muted rounded-full overflow-hidden">
        <div 
          className="h-full bg-purple-500 transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>
    </BaseEventComponent>
  );
};

export const EvaluationCompletedEventComponent: React.FC<{ event: EvaluationCompletedEvent; isAlternate?: boolean }> = ({ event, isAlternate }) => {
  const { results } = event;
  const allPerfect = results.every(r => r.success_rate === 1.0 && !r.is_flaky);
  const hasFlaky = results.some(r => r.is_flaky);
  
  // Only apply semantic background for success or error states
  const semanticBg = allPerfect ? 'bg-green-500/10' : (!allPerfect && !hasFlaky) ? 'bg-red-500/10' : '';
  
  return (
    <BaseEventComponent isAlternate={isAlternate} className={`py-3 px-3 text-sm ${semanticBg}`}>
      <div className="flex items-center gap-2 mb-3">
        {allPerfect ? (
          <TrendingUp className="h-5 w-5 text-green-500 flex-shrink-0 stroke-[2]" />
        ) : hasFlaky ? (
          <AlertTriangle className="h-5 w-5 text-yellow-500 flex-shrink-0 stroke-[2]" />
        ) : (
          <BarChart2 className="h-5 w-5 text-red-500 flex-shrink-0 stroke-[2]" />
        )}
        <span className={allPerfect ? 'text-green-500' : hasFlaky ? 'text-yellow-500' : 'text-foreground'}>
          {allPerfect ? 'Perfect Consistency' : hasFlaky ? 'Flaky Tests Detected' : 'Evaluation Complete'}
        </span>
      </div>
      
      {/* Show results for each scenario */}
      <div className="space-y-2">
        {results.map((result, idx) => (
          <div key={idx} className="p-2 bg-background/50 rounded text-xs">
            <div className="mb-1 flex items-center justify-between text-foreground">
              <span>{result.scenario_name}</span>
              {result.is_flaky && (
                <span className="text-yellow-500 text-xs">⚠ Flaky</span>
              )}
            </div>
            
            <div className="grid grid-cols-2 gap-2 mt-2">
              <div>
                <div className="text-muted-foreground">Success Rate</div>
                <div className={result.success_rate === 1.0 ? 'text-green-500' : result.success_rate > 0.8 ? 'text-yellow-500' : 'text-red-500'}>
                  {(result.success_rate * 100).toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Consistency</div>
                <div className={result.consistency_score === 1.0 ? 'text-green-500' : result.consistency_score > 0.8 ? 'text-yellow-500' : 'text-red-500'}>
                  {(result.consistency_score * 100).toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Runs</div>
                <div className="text-foreground">
                  {result.successful_runs}/{result.total_runs}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Duration</div>
                <div className="text-foreground">
                  {(result.avg_duration * 1000).toFixed(0)}ms ±{(result.std_duration * 1000).toFixed(0)}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </BaseEventComponent>
  );
};


