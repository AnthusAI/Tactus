import React from 'react';
import { Clock } from 'lucide-react';

interface TimestampProps {
  timestamp: string; // ISO timestamp string
  className?: string;
}

export const Timestamp: React.FC<TimestampProps> = ({ timestamp, className = '' }) => {
  const timeString = new Date(timestamp).toLocaleTimeString();
  
  return (
    <span className={`flex items-center gap-1 text-xs text-muted-foreground ${className}`}>
      <Clock className="h-3 w-3 flex-shrink-0" />
      <span>{timeString}</span>
    </span>
  );
};
