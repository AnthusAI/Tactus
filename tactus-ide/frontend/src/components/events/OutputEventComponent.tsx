import React from 'react';
import { OutputEvent } from '@/types/events';
import { cn } from '@/lib/utils';
import { BaseEventComponent } from './BaseEventComponent';

interface OutputEventComponentProps {
  event: OutputEvent;
  isAlternate?: boolean;
}

export const OutputEventComponent: React.FC<OutputEventComponentProps> = ({ event, isAlternate }) => {
  const isStderr = event.stream === 'stderr';
  const content = event.content.trim();
  
  // Skip empty lines
  if (!content) return null;
  
  // Skip Python warnings
  if (content.includes('RequestsDependencyWarning') || content.includes('warnings.warn')) return null;
  
  // Skip internal INFO log lines
  if (content.match(/^\[\d{2}\/\d{2}\/\d{2} \d{2}:\d{2}:\d{2}\]\s+INFO\s+/)) return null;
  
  // Skip Rich box borders (but keep content inside)
  if (content.match(/^[╭╰│─]+$/)) return null;
  if (content.match(/^│\s*(Running procedure:|Lua sandbox)/)) return null;
  
  // Skip agent turn events (shown as LoadingEvent)
  if (content.match(/^⏳ Agent.*Waiting for response/)) return null;
  if (content.match(/^✓ Agent.*Completed \d+ms$/)) return null;
  
  // Skip individual cost lines (keep Cost Summary section)
  if (content.match(/^💰 Cost \w+: \$/)) return null;
  
  // Keep everything else: agent responses, cost summary, results, etc.
  return (
    <BaseEventComponent isAlternate={isAlternate} className={cn('py-1 px-3 font-mono text-xs', isStderr && 'text-red-400')}>
      <pre className="whitespace-pre-wrap break-words">{content}</pre>
    </BaseEventComponent>
  );
};





