import React from 'react';
import { EvaluationsData } from '@/types/metadata';
import { FlaskConical, AlertTriangle } from 'lucide-react';

interface EvaluationsSectionProps {
  evaluations: EvaluationsData | null;
}

export const EvaluationsSection: React.FC<EvaluationsSectionProps> = ({ evaluations }) => {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <FlaskConical className="h-4 w-4 text-muted-foreground" />
        <h3 className="font-semibold text-sm">Evaluations</h3>
      </div>

      {!evaluations ? (
        <div className="ml-6">
          <div className="flex items-center gap-2 px-3 py-2 bg-yellow-500/10 border border-yellow-500/30 rounded-md">
            <AlertTriangle className="h-4 w-4 text-yellow-600 dark:text-yellow-500 flex-shrink-0" />
            <span className="text-sm text-yellow-700 dark:text-yellow-400 font-medium">
              No evaluations defined
            </span>
          </div>
        </div>
      ) : (
        <div className="ml-6 space-y-1">
          <div className="text-sm">
            <span className="text-muted-foreground">Dataset:</span>{' '}
            <span className="text-foreground">{evaluations.dataset_count} {evaluations.dataset_count === 1 ? 'case' : 'cases'}</span>
          </div>

          <div className="text-sm">
            <span className="text-muted-foreground">Evaluators:</span>{' '}
            <span className="text-foreground">{evaluations.evaluator_count}</span>
          </div>

          <div className="text-sm">
            <span className="text-muted-foreground">Runs:</span>{' '}
            <span className="text-foreground">{evaluations.runs}</span>
            {evaluations.parallel && (
              <span className="ml-2 text-xs text-muted-foreground">(parallel)</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
