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
  value,
  onValueChange,
  responded,
}) => {
  const placeholder = item.metadata?.placeholder || 'Enter your response...';
  const [localValue, setLocalValue] = React.useState(value || '');

  // Update local value when prop changes (e.g., form reset)
  React.useEffect(() => {
    setLocalValue(value || '');
  }, [value]);

  const handleChange = (newValue: string) => {
    setLocalValue(newValue);
    onValueChange(newValue);
  };

  // If responded, show the submitted value
  if (responded) {
    return (
      <div className="px-3 py-2 text-sm border rounded-md bg-muted text-foreground">
        {value || '(empty)'}
      </div>
    );
  }

  return (
    <div className="flex gap-2">
      <input
        type="text"
        value={localValue}
        placeholder={placeholder}
        className="flex-1 px-3 py-2 text-sm border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            // In batched mode, Enter just updates the value (Submit All will send)
            // In single mode, this ensures the value is captured
            handleChange((e.target as HTMLInputElement).value);
          }
        }}
      />
      <Button
        onClick={(e) => {
          const input = e.currentTarget.previousElementSibling as HTMLInputElement;
          handleChange(input.value);
        }}
        size="sm"
      >
        Submit
      </Button>
    </div>
  );
};
