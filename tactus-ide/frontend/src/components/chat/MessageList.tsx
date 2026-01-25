import React from 'react';
import { Bot, User, Loader2, Wrench } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Message, MessageContent } from '@/components/ui/ai/message';
import { Badge } from '@/components/ui/badge';
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
  } else if (isThinking) {
    displayContent = '...';
  }

  // All messages use the same Message + MessageContent structure
  // with consistent theme-based styling - NO hardcoded colors
  return (
    <Message from={isUser ? 'user' : 'assistant'}>
      {/* Avatar - consistent theme-based styling for all message types */}
      <div className={cn(
        "rounded-full h-8 w-8 flex items-center justify-center flex-shrink-0",
        isUser ? "bg-primary text-primary-foreground" : "bg-primary/10"
      )}>
        {isThinking ? (
          <Loader2 className="h-4 w-4 text-primary animate-spin" />
        ) : isStatus ? (
          <Wrench className="h-4 w-4 text-muted-foreground" />
        ) : isUser ? (
          <User className="h-4 w-4" />
        ) : (
          <Bot className="h-4 w-4 text-primary" />
        )}
      </div>

      {/* Message content - let MessageContent handle bg-muted styling */}
      <MessageContent>
        {isThinking ? (
          <span className="text-sm text-muted-foreground italic">Thinking...</span>
        ) : isStatus ? (
          <Badge variant="secondary" className="text-xs font-mono">
            <Wrench className="mr-1 h-3 w-3" />
            {statusText}
          </Badge>
        ) : (
          <div className="whitespace-pre-wrap break-words text-sm">
            {displayContent}
          </div>
        )}
      </MessageContent>
    </Message>
  );
};
