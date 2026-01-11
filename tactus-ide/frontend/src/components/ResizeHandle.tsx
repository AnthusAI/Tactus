import React, { useCallback, useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';

interface ResizeHandleProps {
  onResize: (delta: number) => void;
  direction: 'left' | 'right';
  className?: string;
}

export const ResizeHandle: React.FC<ResizeHandleProps> = ({ onResize, direction, className }) => {
  const isDragging = useRef(false);
  const startX = useRef(0);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    startX.current = e.clientX;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      
      const delta = e.clientX - startX.current;
      startX.current = e.clientX;
      
      // For right panel, we need to invert the delta
      onResize(direction === 'right' ? -delta : delta);
    };

    const handleMouseUp = () => {
      if (isDragging.current) {
        isDragging.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [onResize, direction]);

  return (
    <div
      className={cn(
        'relative cursor-col-resize group',
        className
      )}
      style={{ width: '1px' }}
      onMouseDown={handleMouseDown}
      role="separator"
      aria-label={`Resize ${direction} panel`}
    >
      {/* Background line - matches top nav bar border */}
      <div className="absolute inset-0 bg-border" />

      {/* Drag handle oval indicator */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1.5 h-8 border border-border rounded-full bg-card/80 transition-all duration-150 group-hover:scale-110 group-hover:border-primary/50 z-10" />

      {/* Hover effect overlay */}
      <div className="absolute inset-0 group-hover:bg-blue-500/30 transition-colors" />
    </div>
  );
};








