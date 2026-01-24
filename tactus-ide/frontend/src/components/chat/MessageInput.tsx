import React, { useState, useRef, useEffect } from 'react';
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputToolbar,
  PromptInputTools,
  PromptInputSubmit
} from '@/components/ui/ai/prompt-input';
import { cn } from '@/lib/utils';

interface MessageInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export const MessageInput: React.FC<MessageInputProps> = ({
  onSend,
  disabled = false,
  placeholder = 'Send a message...',
}) => {
  const [value, setValue] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim() && !disabled) {
      onSend(value.trim());
      setValue('');
    }
  };

  // Determine status for submit button
  const status = disabled ? 'streaming' : 'ready';

  return (
    <PromptInput onSubmit={handleSubmit}>
      <PromptInputTextarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        minHeight={48}
        maxHeight={164}
      />
      <PromptInputToolbar>
        <PromptInputTools />
        <PromptInputSubmit
          status={status}
          disabled={disabled || !value.trim()}
        />
      </PromptInputToolbar>
    </PromptInput>
  );
};
