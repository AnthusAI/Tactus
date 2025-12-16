import React, { useState, useEffect } from 'react';
import { Timer } from 'lucide-react';
import FlipNumbers from 'react-flip-numbers';

interface DurationProps {
  startTime: string; // ISO timestamp string
  className?: string;
}

export const Duration: React.FC<DurationProps> = ({ startTime, className = '' }) => {
  // Parse timestamp (Unix or ISO string)
  const parseTimestamp = (ts: string): number => {
    // If it looks like a Unix timestamp (number with optional decimal)
    if (/^\d+(\.\d+)?$/.test(ts)) {
      return parseFloat(ts) * 1000; // Convert to milliseconds
    }
    // Otherwise treat as ISO string
    return new Date(ts).getTime();
  };

  // Initialize with calculated elapsed time to avoid showing -1:-1
  const [elapsed, setElapsed] = useState<number>(() => {
    if (!startTime) return 0;
    const start = parseTimestamp(startTime);
    const now = Date.now();
    return Math.max(0, Math.floor((now - start) / 1000));
  });

  useEffect(() => {
    if (!startTime) return;

    const updateDuration = () => {
      const start = parseTimestamp(startTime);
      const now = Date.now();
      const seconds = Math.max(0, Math.floor((now - start) / 1000));
      setElapsed(seconds);
    };

    // Update every second (initial value already set by useState)
    const interval = setInterval(updateDuration, 1000);

    return () => clearInterval(interval);
  }, [startTime]);

  // Format as HH:MM:SS or MM:SS
  const formatDuration = (totalSeconds: number): string => {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (hours > 0) {
      return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }
    return `${minutes}:${String(seconds).padStart(2, '0')}`;
  };

  const durationString = formatDuration(elapsed);

  return (
    <span className={`flex items-center gap-1 text-xs text-muted-foreground ${className}`}>
      <Timer className="h-3 w-3 flex-shrink-0" />
      <span className="tabular-nums">
        {durationString}
      </span>
    </span>
  );
};
