import React, { useState } from 'react';
import { Bell, CheckCircle2 } from 'lucide-react';
import { BaseEventComponent } from './BaseEventComponent';
import { HITLRequestEvent } from '@/types/events';
import { Button } from '../ui/button';

interface HITLEventComponentProps {
  event: HITLRequestEvent;
  isAlternate?: boolean;
  onRespond?: (requestId: string, value: any) => void;
}

/**
 * Component for displaying HITL requests in the IDE event stream.
 *
 * Renders a notification with action buttons based on request type.
 * Integrates with @anthus/tactus-hitl-components for rich UI rendering.
 */
export const HITLEventComponent: React.FC<HITLEventComponentProps> = ({
  event,
  isAlternate,
  onRespond
}) => {
  const [responded, setResponded] = useState(false);
  const [responseValue, setResponseValue] = useState<any>(null);

  const handleResponse = (value: any) => {
    setResponded(true);
    setResponseValue(value);
    if (onRespond) {
      onRespond(event.request_id, value);
    }
  };

  // Convert event to HITLRequest format for @anthus/tactus-hitl-components
  const hitlRequest = {
    request_id: event.request_id,
    procedure_id: event.procedure_id || '',
    procedure_name: event.procedure_name,
    invocation_id: event.invocation_id,
    request_type: event.request_type,
    message: event.message,
    options: event.options,
    items: event.items,
    subject: event.subject,
    input_summary: event.input_summary,
    conversation: event.conversation,
    prior_interactions: event.prior_interactions,
    metadata: event.metadata,
    timeout_seconds: event.timeout_seconds,
    default_value: event.default_value,
  };

  return (
    <BaseEventComponent isAlternate={isAlternate} className="py-3 px-3">
      <div className="flex items-start gap-3">
        {responded ? (
          <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0 stroke-[2.5] mt-0.5" />
        ) : (
          <Bell className="h-5 w-5 text-yellow-600 flex-shrink-0 stroke-[2.5] mt-0.5" />
        )}

        <div className="flex-1 min-w-0 space-y-3">
          {/* Header */}
          <div>
            <div className="flex items-center justify-between">
              <span className="font-semibold text-foreground">
                {responded ? 'Response Sent' : 'Awaiting Human Input'}
              </span>
              <span className="text-xs text-muted-foreground">
                {event.procedure_name}
              </span>
            </div>
            {event.subject && (
              <div className="text-sm text-muted-foreground mt-1">
                {event.subject}
              </div>
            )}
          </div>

          {/* Message */}
          <div className="text-sm text-foreground">
            {event.message}
          </div>

          {/* Response buttons or confirmation */}
          {responded ? (
            <div className="text-sm text-green-600 font-medium">
              ✓ Responded: {JSON.stringify(responseValue)}
            </div>
          ) : (
            <div className="space-y-2">
              {/* Simple approval buttons */}
              {event.request_type === 'approval' && (
                <div className="flex gap-2">
                  {event.options && event.options.length > 0 ? (
                    // Custom options provided
                    event.options.map((option) => (
                      <Button
                        key={option.label}
                        onClick={() => handleResponse(option.value)}
                        variant={option.style === 'danger' ? 'destructive' : option.style === 'primary' ? 'default' : 'secondary'}
                        size="sm"
                      >
                        {option.label}
                      </Button>
                    ))
                  ) : (
                    // Default Yes/No buttons
                    <>
                      <Button
                        onClick={() => handleResponse(true)}
                        variant="default"
                        size="sm"
                      >
                        Approve
                      </Button>
                      <Button
                        onClick={() => handleResponse(false)}
                        variant="secondary"
                        size="sm"
                      >
                        Reject
                      </Button>
                    </>
                  )}
                </div>
              )}

              {/* Simple input */}
              {event.request_type === 'input' && (
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Enter your response..."
                    className="flex-1 px-3 py-2 text-sm border rounded-md"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleResponse((e.target as HTMLInputElement).value);
                      }
                    }}
                  />
                  <Button
                    onClick={(e) => {
                      const input = e.currentTarget.previousElementSibling as HTMLInputElement;
                      handleResponse(input.value);
                    }}
                    size="sm"
                  >
                    Submit
                  </Button>
                </div>
              )}

              {/* Select options */}
              {event.request_type === 'select' && event.options && (
                <div className="flex gap-2 flex-wrap">
                  {event.options.map((option) => (
                    <Button
                      key={option.label}
                      onClick={() => handleResponse(option.value)}
                      variant="outline"
                      size="sm"
                    >
                      {option.label}
                    </Button>
                  ))}
                </div>
              )}

              {/* Batched inputs - show a simplified indicator */}
              {event.request_type === 'inputs' && event.items && (
                <div className="text-sm text-muted-foreground">
                  Multiple inputs required ({event.items.length} items)
                  <Button
                    onClick={() => {
                      // TODO: Open modal with full HITLInputsPanel
                      alert('Batched inputs UI not yet implemented in inline view');
                    }}
                    variant="outline"
                    size="sm"
                    className="ml-2"
                  >
                    Open Form
                  </Button>
                </div>
              )}

              {/* Fallback for other types */}
              {!['approval', 'input', 'select', 'inputs'].includes(event.request_type) && (
                <div className="text-sm text-muted-foreground">
                  {event.request_type} request (custom UI needed)
                </div>
              )}
            </div>
          )}

          {/* Context indicators */}
          {!responded && (
            <div className="flex gap-3 text-xs text-muted-foreground">
              {event.input_summary && (
                <span>📋 Input context available</span>
              )}
              {event.conversation && event.conversation.length > 0 && (
                <span>💬 {event.conversation.length} messages</span>
              )}
              {event.prior_interactions && event.prior_interactions.length > 0 && (
                <span>🔄 {event.prior_interactions.length} prior interactions</span>
              )}
            </div>
          )}
        </div>
      </div>
    </BaseEventComponent>
  );
};
