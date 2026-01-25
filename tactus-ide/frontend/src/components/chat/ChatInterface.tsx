import React, { useState, useEffect } from 'react';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { useChatSSE } from '@/hooks/useChatSSE';
import { Loader2 } from 'lucide-react';
import { Conversation, ConversationContent, ConversationScrollButton } from '@/components/ui/ai/conversation';

interface ChatInterfaceProps {
  workspaceRoot: string;
}

export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant' | 'system' | 'tool_call' | 'tool_result' | 'error';
  content: string;
  metadata?: any;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ workspaceRoot }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isConnecting, setIsConnecting] = useState(true);
  
  const {
    messages: sseMessages,
    isLoading,
    error: sseError,
    sendMessage,
  } = useChatSSE(workspaceRoot, {
    provider: 'openai',
    model: 'gpt-4o',
    temperature: 0.7,
    max_tokens: 4000,
  });

  // Sync SSE messages with local messages state
  useEffect(() => {
    if (sseMessages.length > 0) {
      const formattedMessages: ChatMessage[] = sseMessages.map((msg, idx) => ({
        id: `${Date.now()}-${idx}`,
        type: msg.role,
        content: msg.content,
      }));
      setMessages(formattedMessages);
    }
  }, [sseMessages]);

  // Mark as connected immediately (no WebSocket handshake needed)
  useEffect(() => {
    setIsConnecting(false);
  }, []);

  const handleSendMessage = async (content: string) => {
    await sendMessage(content);
  };

  if (isConnecting) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" />
          <span className="text-sm">Initializing chat...</span>
        </div>
      </div>
    );
  }

  if (sseError) {
    return (
      <div className="flex items-center justify-center h-full p-4">
        <div className="text-center max-w-md space-y-2">
          <p className="text-sm font-medium text-destructive">Connection Error</p>
          <p className="text-xs text-muted-foreground">{sseError}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Messages Area with Conversation wrapper for auto-scroll */}
      <Conversation className="flex-1">
        <ConversationContent>
          <MessageList messages={messages} />
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      {/* Input Area */}
      <div className="border-t bg-background p-4">
        <div className="max-w-3xl mx-auto">
          <MessageInput
            onSend={handleSendMessage}
            disabled={isLoading}
            placeholder={isLoading ? 'Waiting for response...' : 'Send a message...'}
          />
        </div>
      </div>
    </div>
  );
};
