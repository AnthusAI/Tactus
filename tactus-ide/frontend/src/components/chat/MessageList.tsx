import React from 'react';
import { Bot, User, Loader2, Wrench } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatMessage } from './ChatInterface';

interface MessageListProps {
  messages: ChatMessage[];
}

export const MessageList: React.FC<MessageListProps> = ({ messages }) => {
  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-4">
        <div className="max-w-md space-y-4">
          <div className="flex justify-center">
            <div className="rounded-full bg-primary/10 p-4">
              <Bot className="h-8 w-8 text-primary" />
            </div>
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-semibold">How can I help you today?</h3>
            <p className="text-sm text-muted-foreground">
              I can help you understand Tactus procedures, read and analyze files, or answer questions about your code.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 px-4 py-6">
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} />
      ))}
    </div>
  );
};

interface MessageItemProps {
  message: ChatMessage;
}

const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  const isUser = message.type === 'user';
  const isThinking = message.content.startsWith('_thinking_');
  const isStatus = message.content.startsWith('_status_');
  
  let displayContent = message.content;
  let statusText = '';
  
  if (isStatus) {
    statusText = message.content.replace(/^_status_/, '');
    displayContent = '';
  } else if (isThinking) {
    displayContent = '...';
  }

  if (isThinking) {
    return (
      <div className="flex gap-3 items-start">
        <div className="flex-shrink-0 mt-1">
          <div className="rounded-full bg-primary/10 p-2">
            <Loader2 className="h-4 w-4 text-primary animate-spin" />
          </div>
        </div>
        <div className="flex-1 space-y-2 pt-1">
          <div className="text-sm text-muted-foreground italic">
            Thinking...
          </div>
        </div>
      </div>
    );
  }

  if (isStatus) {
    return (
      <div className="flex gap-3 items-start">
        <div className="flex-shrink-0 mt-1">
          <div className="rounded-full bg-blue-500/10 p-2">
            <Wrench className="h-4 w-4 text-blue-500" />
          </div>
        </div>
        <div className="flex-1 space-y-2 pt-1">
          <div className="text-xs font-mono text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/30 px-2 py-1 rounded">
            {statusText}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex gap-3 items-start", isUser && "flex-row-reverse")}>
      {/* Avatar */}
      <div className="flex-shrink-0 mt-1">
        <div className={cn(
          "rounded-full p-2",
          isUser ? "bg-primary text-primary-foreground" : "bg-primary/10"
        )}>
          {isUser ? (
            <User className="h-4 w-4" />
          ) : (
            <Bot className="h-4 w-4 text-primary" />
          )}
        </div>
      </div>

      {/* Message Content */}
      <div className={cn(
        "flex-1 space-y-2 overflow-hidden",
        isUser && "flex flex-col items-end"
      )}>
        <div className={cn(
          "inline-block rounded-lg px-4 py-2.5 text-sm",
          "bg-muted/50 text-foreground"
        )}>
          <div className="whitespace-pre-wrap break-words">
            {displayContent}
          </div>
        </div>
      </div>
    </div>
  );
};
