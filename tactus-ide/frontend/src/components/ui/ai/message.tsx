import * as React from 'react';
import { cn } from '@/lib/utils';

export type MessageProps = React.HTMLAttributes<HTMLDivElement> & {
  from: 'user' | 'assistant';
};

export const Message = React.forwardRef<HTMLDivElement, MessageProps>(
  ({ className, from, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex gap-3 py-2',
        from === 'user' && 'flex-row-reverse',
        className
      )}
      {...props}
    />
  )
);
Message.displayName = 'Message';

export type MessageContentProps = React.HTMLAttributes<HTMLDivElement>;

export const MessageContent = React.forwardRef<HTMLDivElement, MessageContentProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('flex-1 rounded-lg bg-muted px-3 py-2 text-sm', className)}
      {...props}
    />
  )
);
MessageContent.displayName = 'MessageContent';

export type MessageAvatarProps = React.ImgHTMLAttributes<HTMLImageElement> & {
  name?: string;
};

export const MessageAvatar = React.forwardRef<HTMLImageElement, MessageAvatarProps>(
  ({ className, name, ...props }, ref) => (
    <img
      ref={ref}
      className={cn('h-8 w-8 rounded-full', className)}
      alt={name || 'Avatar'}
      {...props}
    />
  )
);
MessageAvatar.displayName = 'MessageAvatar';









