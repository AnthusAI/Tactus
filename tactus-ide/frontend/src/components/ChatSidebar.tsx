import React from 'react';
import { ChatInterface } from './chat/ChatInterface';

interface ChatSidebarProps {
  apiUrl: (path: string) => string;
  onClose?: () => void;
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({ apiUrl, onClose }) => {
  // TODO: Get workspace root from context/props
  const workspaceRoot = '/Users/ryan.porter/Projects/Tactus_4';
  
  return <ChatInterface workspaceRoot={workspaceRoot} />;
};
