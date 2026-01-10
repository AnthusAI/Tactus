import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Button } from './ui/button';
import { Separator } from './ui/separator';
import { Bot, Trash2, X } from 'lucide-react';
import { Conversation, ConversationContent, ConversationScrollButton } from './ui/ai/conversation';
import { Message, MessageContent } from './ui/ai/message';
import { PromptInput, PromptInputTextarea, PromptInputToolbar, PromptInputSubmit } from './ui/ai/prompt-input';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface ChatSidebarProps {
  apiUrl: (path: string) => string;
  onClose?: () => void;
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({ apiUrl, onClose }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const addMessage = useCallback((role: 'user' | 'assistant', content: string) => {
    const newMessage: ChatMessage = {
      id: `${Date.now()}-${Math.random()}`,
      role,
      content,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, newMessage]);
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      if (!inputValue.trim() || isLoading) {
        return;
      }

      const userMessage = inputValue.trim();
      setInputValue('');
      setError(null);

      // Add user message immediately
      addMessage('user', userMessage);
      setIsLoading(true);

      try {
        // Send message to backend
        const response = await fetch(apiUrl('/api/chat'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ message: userMessage }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || 'Failed to send message');
        }

        const data = await response.json();

        // Add assistant response
        if (data.response) {
          addMessage('assistant', data.response);
        }
      } catch (err) {
        console.error('Error sending message:', err);
        const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
        setError(errorMessage);
        addMessage('assistant', `Error: ${errorMessage}`);
      } finally {
        setIsLoading(false);
        // Focus textarea after response
        setTimeout(() => {
          textareaRef.current?.focus();
        }, 100);
      }
    },
    [inputValue, isLoading, addMessage, apiUrl]
  );

  const handleClearChat = useCallback(async () => {
    try {
      await fetch(apiUrl('/api/chat/reset'), {
        method: 'POST',
      });
      setMessages([]);
      setError(null);
    } catch (err) {
      console.error('Error clearing chat:', err);
    }
  }, [apiUrl]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
  }, []);

  // Auto-focus textarea on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const submitStatus = isLoading ? 'submitted' : error ? 'error' : 'ready';

  return (
    <div className="flex flex-col h-full bg-card">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-primary" />
          <h2 className="text-sm font-semibold">AI Assistant</h2>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleClearChat}
            disabled={messages.length === 0}
            className="h-8 w-8"
            title="Clear chat"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
          {onClose && (
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="h-8 w-8"
              title="Close sidebar"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Messages */}
      <Conversation className="flex-1">
        <ConversationContent>
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground p-8">
              <Bot className="h-12 w-12 mb-4 opacity-50" />
              <p className="text-sm mb-2">AI Coding Assistant</p>
              <p className="text-xs">
                Ask me to read files, write code, explain concepts, or help with debugging.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((message) => (
                <Message key={message.id} from={message.role}>
                  <MessageContent>
                    <div className="whitespace-pre-wrap break-words">
                      {message.content}
                    </div>
                  </MessageContent>
                </Message>
              ))}
            </div>
          )}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <Separator />

      {/* Input */}
      <div className="p-4">
        <PromptInput onSubmit={handleSubmit}>
          <PromptInputTextarea
            ref={textareaRef}
            value={inputValue}
            onChange={handleInputChange}
            placeholder="Ask me anything about your code..."
            disabled={isLoading}
          />
          <PromptInputToolbar>
            <div className="flex-1" />
            <PromptInputSubmit status={submitStatus} disabled={!inputValue.trim() || isLoading} />
          </PromptInputToolbar>
        </PromptInput>
      </div>
    </div>
  );
};
