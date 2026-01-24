/**
 * Built-in Input Component
 *
 * Renders a simple text input field with submit button.
 * Supports placeholder text via metadata.
 */

import React from 'react';
import { Button } from '@/components/ui/button';
import { HITLComponentRendererProps } from '../../types';

export const InputComponent: React.FC<HITLComponentRendererProps> = ({
  item,
  onValueChange,
}) => {
  const placeholder = item.metadata?.placeholder || 'Enter your response...';

  return (
    <div className="flex gap-2">
      <input
        type="text"
        placeholder={placeholder}
        className="flex-1 px-3 py-2 text-sm border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            onValueChange((e.target as HTMLInputElement).value);
          }
        }}
      />
      <Button
        onClick={(e) => {
          const input = e.currentTarget.previousElementSibling as HTMLInputElement;
          onValueChange(input.value);
        }}
        size="sm"
      >
        Submit
      </Button>
    </div>
  );
};
