import React, { useState } from 'react';
import { SpecificationsData } from '@/types/metadata';
import { ListChecks, ChevronDown, ChevronRight, AlertTriangle } from 'lucide-react';

interface SpecificationsSectionProps {
  specifications: SpecificationsData | null;
}

export const SpecificationsSection: React.FC<SpecificationsSectionProps> = ({ specifications }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <ListChecks className="h-4 w-4 text-muted-foreground" />
        <h3 className="font-semibold text-sm">Specifications</h3>
      </div>

      {!specifications ? (
        <div className="ml-6">
          <div className="flex items-center gap-2 px-3 py-2 bg-yellow-500/10 border border-yellow-500/30 rounded-md">
            <AlertTriangle className="h-4 w-4 text-yellow-600 dark:text-yellow-500 flex-shrink-0" />
            <span className="text-sm text-yellow-700 dark:text-yellow-400 font-medium">
              No test specifications defined
            </span>
          </div>
        </div>
      ) : (
        <div className="ml-6 space-y-1">
          {specifications.feature_name && (
            <div className="text-sm">
              <span className="text-muted-foreground">Feature:</span>{' '}
              <span className="text-foreground">{specifications.feature_name}</span>
            </div>
          )}

          <div className="text-sm text-muted-foreground">
            {specifications.scenario_count} {specifications.scenario_count === 1 ? 'scenario' : 'scenarios'}
          </div>

          {/* Expandable Gherkin text */}
          <div>
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mt-2"
            >
              {expanded ? (
                <>
                  <ChevronDown className="h-3 w-3" />
                  Hide details
                </>
              ) : (
                <>
                  <ChevronRight className="h-3 w-3" />
                  Show details
                </>
              )}
            </button>

            {expanded && (
              <pre className="mt-2 text-xs font-mono bg-muted/30 rounded p-2 overflow-x-auto whitespace-pre-wrap">
                {specifications.text}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
