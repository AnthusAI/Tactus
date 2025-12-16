import React from 'react';
import { Clock } from 'lucide-react';

interface TimestampProps {
  timestamp: string; // ISO timestamp string
  className?: string;
}

export const Timestamp: React.FC<TimestampProps> = ({ timestamp, className = '' }) => {
  // Handle both Unix timestamp (number as string) and ISO string formats
  const parseTimestamp = (ts: string): Date => {
    if (!ts) {
      console.warn('Timestamp component received empty timestamp');
      return new Date();
    }

    // If it looks like a Unix timestamp (number with optional decimal)
    if (/^\d+(\.\d+)?$/.test(ts)) {
      return new Date(parseFloat(ts) * 1000);
    }
    // Otherwise treat as ISO string
    const date = new Date(ts);
    if (isNaN(date.getTime())) {
      console.warn('Timestamp component failed to parse:', ts);
    }
    return date;
  };

  const date = parseTimestamp(timestamp);
  const timeString = isNaN(date.getTime()) ? 'Invalid' : date.toLocaleTimeString();

  return (
    <span className={`flex items-center gap-1 text-xs text-muted-foreground ${className}`}>
      <Clock className="h-3 w-3 flex-shrink-0" />
      <span>{timeString}</span>
    </span>
  );
};
