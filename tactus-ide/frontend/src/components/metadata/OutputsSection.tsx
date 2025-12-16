import React from 'react';
import { OutputFieldDeclaration } from '@/types/metadata';
import { FileOutput } from 'lucide-react';

interface OutputsSectionProps {
  outputs: Record<string, OutputFieldDeclaration>;
}

export const OutputsSection: React.FC<OutputsSectionProps> = ({ outputs }) => {
  const outputList = Object.values(outputs);

  if (outputList.length === 0) {
    return null;
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <FileOutput className="h-4 w-4" />
        <h3 className="font-semibold text-sm">Outputs</h3>
      </div>
      <div className="space-y-2">
        {outputList.map((output) => (
          <div key={output.name} className="pl-4 border-l-2 border-muted">
            <div className="flex items-center gap-2">
              <code className="text-sm font-mono">{output.name}</code>
              <span className="text-xs text-muted-foreground">
                {output.type}
              </span>
              {output.required && (
                <span className="text-xs text-muted-foreground">required</span>
              )}
            </div>
            {output.description && (
              <p className="text-xs text-muted-foreground mt-1">{output.description}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
