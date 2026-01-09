import React from 'react';
import { ParameterDeclaration } from '@/types/metadata';
import { FileInput, Hash, Type } from 'lucide-react';

interface ParametersSectionProps {
  parameters: Record<string, ParameterDeclaration>;
}

export const ParametersSection: React.FC<ParametersSectionProps> = ({ parameters }) => {
  const paramList = Object.entries(parameters ?? {})
    .map(([name, param]) => {
      if (!param || typeof param !== 'object') {
        return null;
      }
      return { ...param, name: param.name ?? name };
    })
    .filter((param): param is ParameterDeclaration => param !== null);

  if (paramList.length === 0) {
    return null;
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <FileInput className="h-4 w-4" />
        <h3 className="font-semibold text-sm">Input</h3>
      </div>
      <div className="space-y-2">
        {paramList.map((param) => (
          <div key={param.name} className="pl-4 border-l-2 border-muted">
            <div className="flex items-center gap-2">
              <code className="text-sm font-mono">{param.name}</code>
              <span className="text-xs text-muted-foreground">
                {param.type}
              </span>
              {param.required && (
                <span className="text-xs text-muted-foreground">required</span>
              )}
            </div>
            {param.default !== undefined && (
              <div className="text-xs text-muted-foreground mt-0.5">
                Default: <code className="text-xs">{JSON.stringify(param.default)}</code>
              </div>
            )}
            {param.description && (
              <p className="text-xs text-muted-foreground mt-1">{param.description}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
