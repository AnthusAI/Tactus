/**
 * Built-in Select Component
 *
 * Renders a button grid for selecting from multiple options.
 * Supports both single-select and multi-select modes based on metadata.
 */

import React from 'react';
import { Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { HITLComponentRendererProps } from '../../types';

export const SelectComponent: React.FC<HITLComponentRendererProps> = ({
  item,
  value,
  onValueChange,
}) => {
  if (!item.options || item.options.length === 0) {
    return (
      <div className="text-sm text-muted-foreground">
        No options provided
      </div>
    );
  }

  const isMultiple = item.metadata?.mode === 'multiple';

  return (
    <div className="grid grid-cols-2 gap-2">
      {item.options.map((option) => {
        // Check if this option is selected
        const isSelected = isMultiple
          ? Array.isArray(value) && value.includes(option.value)
          : value === option.value;

        return (
          <Button
            key={option.label}
            onClick={() => {
              if (isMultiple) {
                // Multi-select: toggle value in array
                const currentArray = Array.isArray(value) ? value : [];
                const newValue = currentArray.includes(option.value)
                  ? currentArray.filter((v: string) => v !== option.value)
                  : [...currentArray, option.value];
                onValueChange(newValue);
              } else {
                // Single select: set value
                onValueChange(option.value);
              }
            }}
            variant={isSelected ? 'default' : 'outline'}
            size="sm"
            className="w-full justify-start"
          >
            {isMultiple && isSelected && <Check className="h-4 w-4 mr-2" />}
            {option.label}
          </Button>
        );
      })}
    </div>
  );
};
