import React from 'react';
import { 
  EvaluationStartedEvent, 
  EvaluationCompletedEvent,
  EvaluationProgressEvent 
} from '@/types/events';
import { BarChart2, TrendingUp, AlertTriangle } from 'lucide-react';

export const EvaluationStartedEventComponent: React.FC<{ event: EvaluationStartedEvent }> = ({ event }) => {
  return (
    <div className="py-2 px-3 border-b border-border/50 bg-purple-500/10">
      <div className="flex items-center gap-2">
        <BarChart2 className="h-4 w-4 text-purple-400" />
        <span className="font-medium text-purple-400">Evaluation Started</span>
      </div>
      <div className="text-sm text-muted-foreground mt-1">
        Running {event.total_scenarios} scenario{event.total_scenarios !== 1 ? 's' : ''} × {event.runs_per_scenario} times
      </div>
    </div>
  );
};

export const EvaluationProgressEventComponent: React.FC<{ event: EvaluationProgressEvent }> = ({ event }) => {
  const progress = (event.completed_runs / event.total_runs) * 100;
  
  return (
    <div className="py-1.5 px-3 border-b border-border/50 bg-muted/30">
      <div className="flex items-center gap-2">
        <div className="text-sm font-medium">{event.scenario_name}</div>
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
    </div>
  );
};

export const EvaluationCompletedEventComponent: React.FC<{ event: EvaluationCompletedEvent }> = ({ event }) => {
  const { results } = event;
  const allPerfect = results.every(r => r.success_rate === 1.0 && !r.is_flaky);
  const hasFlaky = results.some(r => r.is_flaky);
  
  return (
    <div className={`py-3 px-3 border-b border-border/50 ${allPerfect ? 'bg-green-500/10' : hasFlaky ? 'bg-yellow-500/10' : 'bg-red-500/10'}`}>
      <div className="flex items-center gap-2 mb-3">
        {allPerfect ? (
          <TrendingUp className="h-5 w-5 text-green-500" />
        ) : hasFlaky ? (
          <AlertTriangle className="h-5 w-5 text-yellow-500" />
        ) : (
          <BarChart2 className="h-5 w-5 text-red-500" />
        )}
        <span className="font-semibold">
          {allPerfect ? 'Perfect Consistency' : hasFlaky ? 'Flaky Tests Detected' : 'Evaluation Complete'}
        </span>
      </div>
      
      {/* Show results for each scenario */}
      <div className="space-y-2">
        {results.map((result, idx) => (
          <div key={idx} className="p-2 bg-background/50 rounded text-xs">
            <div className="font-medium mb-1 flex items-center justify-between">
              <span>{result.scenario_name}</span>
              {result.is_flaky && (
                <span className="text-yellow-500 text-xs">⚠ Flaky</span>
              )}
            </div>
            
            <div className="grid grid-cols-2 gap-2 mt-2">
              <div>
                <div className="text-muted-foreground">Success Rate</div>
                <div className={`font-medium ${result.success_rate === 1.0 ? 'text-green-500' : result.success_rate > 0.8 ? 'text-yellow-500' : 'text-red-500'}`}>
                  {(result.success_rate * 100).toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Consistency</div>
                <div className={`font-medium ${result.consistency_score === 1.0 ? 'text-green-500' : result.consistency_score > 0.8 ? 'text-yellow-500' : 'text-red-500'}`}>
                  {(result.consistency_score * 100).toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Runs</div>
                <div className="font-medium">
                  {result.successful_runs}/{result.total_runs}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Duration</div>
                <div className="font-medium">
                  {(result.avg_duration * 1000).toFixed(0)}ms ±{(result.std_duration * 1000).toFixed(0)}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
