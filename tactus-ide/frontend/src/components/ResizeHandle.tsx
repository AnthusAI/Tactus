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
        'relative w-1 hover:w-1.5 transition-all cursor-col-resize group',
        'hover:bg-blue-500/50',
        className
      )}
      onMouseDown={handleMouseDown}
    >
      <div className="absolute inset-0 hover:bg-blue-500/30" />
    </div>
  );
};







