import * as React from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Loader2Icon, SendIcon, SquareIcon, XIcon } from 'lucide-react';

export type PromptInputProps = React.FormHTMLAttributes<HTMLFormElement>;

export const PromptInput = ({ className, ...props }: PromptInputProps) => (
  <form
    className={cn(
      'w-full overflow-hidden rounded-xl border bg-background shadow-sm',
      className
    )}
    {...props}
  />
);

export type PromptInputTextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  minHeight?: number;
  maxHeight?: number;
};

export const PromptInputTextarea = React.forwardRef<HTMLTextAreaElement, PromptInputTextareaProps>(
  ({ onChange, className, placeholder = 'Type your message...', minHeight = 48, maxHeight = 164, ...props }, ref) => {
    const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
      if (e.key === 'Enter') {
        if (e.shiftKey) {
          return;
        }
        e.preventDefault();
        const form = e.currentTarget.form;
        if (form) {
          form.requestSubmit();
        }
      }
    };

    return (
      <textarea
        ref={ref}
        className={cn(
          'w-full resize-none rounded-none border-none p-3 shadow-none outline-none ring-0',
          'max-h-[6lh] bg-transparent dark:bg-transparent',
          'focus-visible:ring-0',
          className
        )}
        name="message"
        onChange={onChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={2}
        {...props}
      />
    );
  }
);
PromptInputTextarea.displayName = 'PromptInputTextarea';

export type PromptInputToolbarProps = React.HTMLAttributes<HTMLDivElement>;

export const PromptInputToolbar = ({ className, ...props }: PromptInputToolbarProps) => (
  <div className={cn('flex items-center justify-between p-1', className)} {...props} />
);

export type PromptInputToolsProps = React.HTMLAttributes<HTMLDivElement>;

export const PromptInputTools = ({ className, ...props }: PromptInputToolsProps) => (
  <div className={cn('flex items-center gap-1', className)} {...props} />
);

export type PromptInputSubmitProps = React.ComponentPropsWithoutRef<typeof Button> & {
  status?: 'submitted' | 'streaming' | 'ready' | 'error';
};

export const PromptInputSubmit = React.forwardRef<HTMLButtonElement, PromptInputSubmitProps>(
  ({ className, variant = 'default', size = 'icon', status, children, ...props }, ref) => {
    let Icon = <SendIcon className="size-4" />;
    if (status === 'submitted') {
      Icon = <Loader2Icon className="size-4 animate-spin" />;
    } else if (status === 'streaming') {
      Icon = <SquareIcon className="size-4" />;
    } else if (status === 'error') {
      Icon = <XIcon className="size-4" />;
    }

    return (
      <Button
        ref={ref}
        className={cn('gap-1.5 rounded-lg', className)}
        size={size}
        type="submit"
        variant={variant}
        {...props}
      >
        {children ?? Icon}
      </Button>
    );
  }
);
PromptInputSubmit.displayName = 'PromptInputSubmit';









