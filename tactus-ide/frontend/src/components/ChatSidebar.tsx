import React from 'react';
import { ChatInterface } from './chat/ChatInterface';

interface ChatSidebarProps {
  apiUrl: (path: string) => string;
  workspaceRoot: string | null;
  onClose?: () => void;
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({ apiUrl, workspaceRoot, onClose }) => {
  // Don't render chat if no workspace is open
  if (!workspaceRoot) {
    return (
      <div className="flex items-center justify-center h-full p-4 text-center">
        <div className="text-sm text-muted-foreground">
          <p className="font-medium mb-2">No workspace open</p>
          <p>Open a folder to start chatting with the AI assistant.</p>
        </div>
      </div>
    );
  }
  
  return <ChatInterface workspaceRoot={workspaceRoot} />;
};
