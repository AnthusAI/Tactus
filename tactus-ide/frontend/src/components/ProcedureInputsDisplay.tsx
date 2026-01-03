import React from 'react';
import { FileInput } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ProcedureInputsDisplayProps {
  inputs: Record<string, any>;
  className?: string;
}

/**
 * Read-only display component for showing procedure inputs.
 * Used in the results sidebar to show what inputs were used for a run.
 */
export const ProcedureInputsDisplay: React.FC<ProcedureInputsDisplayProps> = ({
  inputs,
  className,
}) => {
  const entries = Object.entries(inputs);

  if (entries.length === 0) {
    return null;
  }

  const formatValue = (value: any): string => {
    if (value === null || value === undefined) {
      return 'null';
    }
    if (typeof value === 'object') {
      return JSON.stringify(value);
    }
    if (typeof value === 'boolean') {
      return value ? 'true' : 'false';
    }
    return String(value);
  };

  const getTypeColor = (value: any): string => {
    if (value === null || value === undefined) {
      return 'text-muted-foreground';
    }
    if (typeof value === 'boolean') {
      return value ? 'text-green-500' : 'text-red-500';
    }
    if (typeof value === 'number') {
      return 'text-blue-500';
    }
    if (Array.isArray(value)) {
      return 'text-purple-500';
    }
    if (typeof value === 'object') {
      return 'text-orange-500';
    }
    return 'text-foreground';
  };

  return (
    <div className={cn('py-2 px-3 border-b border-border/50 bg-muted/30', className)}>
      <div className="flex items-center gap-2 mb-2">
        <FileInput className="h-4 w-4 text-muted-foreground" />
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Inputs
        </span>
      </div>
      <div className="space-y-1">
        {entries.map(([name, value]) => (
          <div key={name} className="flex items-baseline gap-2 text-sm">
            <code className="text-xs font-mono text-muted-foreground flex-shrink-0">
              {name}:
            </code>
            <span
              className={cn(
                'text-xs font-mono truncate',
                getTypeColor(value)
              )}
              title={formatValue(value)}
            >
              {formatValue(value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
