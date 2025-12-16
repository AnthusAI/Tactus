import React from 'react';
import { Layers } from 'lucide-react';

interface StagesSectionProps {
  stages: string[];
}

export const StagesSection: React.FC<StagesSectionProps> = ({ stages }) => {
  if (!stages || stages.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Layers className="h-4 w-4 text-muted-foreground" />
        <h3 className="font-semibold text-sm">Stages</h3>
      </div>

      <div className="ml-6">
        <div className="flex flex-wrap gap-2">
          {stages.map((stage, index) => (
            <span
              key={index}
              className="inline-flex items-center px-2 py-1 rounded text-xs bg-muted text-muted-foreground"
            >
              {stage}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};
