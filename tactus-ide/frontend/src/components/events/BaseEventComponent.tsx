import React, { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface BaseEventProps {
  isAlternate?: boolean;
  className?: string;
  children: ReactNode;
}

export const BaseEventComponent: React.FC<BaseEventProps> = ({
  isAlternate = false,
  className,
  children
}) => {
  return (
    <div className={cn(
      'border-b border-border/50',
      isAlternate ? 'bg-feed-row-alternate' : 'bg-feed-row',
      className
    )}>
      {children}
    </div>
  );
};
