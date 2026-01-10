import { useState, useCallback, useRef } from 'react';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface ChatConfig {
  provider: string;
  model: string;
  temperature?: number;
  max_tokens?: number;
}

export function useChatSSE(workspaceRoot: string, config: ChatConfig) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (userMessage: string) => {
    // Add user message immediately
    const userMsg: ChatMessage = {
      role: 'user',
      content: userMessage,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);
    setError(null);

    // Create abort controller for this request
    abortControllerRef.current = new AbortController();

    try {
      const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:5003';
      const response = await fetch(`${backendUrl}/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          workspace_root: workspaceRoot,
          message: userMessage,
          config,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      // Read SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = '';
      let hasAssistantMessage = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            try {
              const event = JSON.parse(data);
              
              if (event.type === 'thinking') {
                // Show thinking indicator immediately
                console.log('[SSE] Received thinking event:', event);
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMsg = newMessages[newMessages.length - 1];
                  if (lastMsg && lastMsg.role === 'assistant' && lastMsg.content.startsWith('_thinking_')) {
                    // Already showing thinking
                    console.log('[SSE] Already showing thinking indicator');
                  } else {
                    console.log('[SSE] Adding thinking indicator');
                    newMessages.push({
                      role: 'assistant',
                      content: '_thinking_...',
                      timestamp: new Date(),
                    });
                  }
                  return newMessages;
                });
              } else if (event.type === 'message' && event.role === 'assistant') {
                // Accumulate chunk
                const chunk = event.content || '';
                assistantMessage += chunk;
                hasAssistantMessage = true;
                
                console.log('[SSE] Received chunk:', chunk.substring(0, 50), '... (total:', assistantMessage.length, 'chars)');
                
                // Update assistant message in real-time (append chunk)
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMsg = newMessages[newMessages.length - 1];
                  
                  // Remove thinking indicator if present
                  if (lastMsg && lastMsg.role === 'assistant' && lastMsg.content.startsWith('_thinking_')) {
                    console.log('[SSE] Removing thinking indicator, starting real message');
                    newMessages.pop();
                  }
                  
                  // Find or create assistant message
                  const assistantMsgIndex = newMessages.findLastIndex(
                    msg => msg.role === 'assistant' && !msg.content.startsWith('_thinking_')
                  );
                  
                  if (assistantMsgIndex >= 0) {
                    // Append chunk to existing message
                    newMessages[assistantMsgIndex].content += chunk;
                  } else {
                    // Create new assistant message with this chunk
                    newMessages.push({
                      role: 'assistant',
                      content: chunk,
                      timestamp: new Date(),
                    });
                  }
                  
                  return newMessages;
                });
              } else if (event.type === 'done') {
                // Stream complete
                setIsLoading(false);
              } else if (event.type === 'error') {
                throw new Error(event.error || 'Unknown error');
              }
            } catch (e) {
              console.error('Error parsing SSE event:', e);
            }
          }
        }
      }

      setIsLoading(false);
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Request aborted');
      } else {
        console.error('Error sending message:', err);
        setError(err.message || 'Failed to send message');
      }
      setIsLoading(false);
    }
  }, [workspaceRoot, config]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  const cancelRequest = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
    }
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
    cancelRequest,
  };
}
