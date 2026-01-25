import React, { useState } from 'react';
import { Bell, CheckCircle2, FileCode, Clock, ExternalLink, RotateCw } from 'lucide-react';
import { BaseEventComponent } from './BaseEventComponent';
import { HITLRequestEvent } from '@/types/events';
import {
  HITLInputsModal,
  HITLInputsPanel,
  HITLRequestRenderer,
} from '@anthus/tactus-hitl-components';
import { Button } from '../ui/button';
import { getComponentRenderer } from '../hitl/registry';

export type HITLDisplayMode = 'inline' | 'standalone';

interface HITLEventComponentProps {
  event: HITLRequestEvent;
  isAlternate?: boolean;
  onRespond?: (requestId: string, value: any) => void;
  /**
   * Display mode:
   * - 'inline': Shows runtime context (source line, elapsed time). Used in IDE event stream.
   * - 'standalone': Shows runtime context + application context (domain-specific links). Used in unified inbox.
   */
  displayMode?: HITLDisplayMode;
}

/**
 * Format elapsed time as human-readable string
 */
function formatElapsedTime(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

/**
 * Component for displaying HITL requests.
 *
 * Uses a registry-based architecture for rendering different HITL request types.
 * Built-in types (approval, input, select), standard library types (image-selector),
 * and application-registered types all use the same unified rendering mechanism.
 *
 * Supports two display modes:
 * - 'inline': For IDE event stream - shows runtime context (source line, elapsed time, checkpoint)
 * - 'standalone': For unified inbox/notifications - shows runtime context + application context
 */
export const HITLEventComponent: React.FC<HITLEventComponentProps> = ({
  event,
  isAlternate,
  onRespond,
  displayMode = 'inline'
}) => {
  const [responded, setResponded] = useState(false);
  const [responseValue, setResponseValue] = useState<any>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [batchedInputsMode, setBatchedInputsMode] = useState<'inline' | 'modal'>('inline');

  // Reset form values when a new event arrives
  React.useEffect(() => {
    setResponded(false);
    setResponseValue(null);
    // Auto-open modal for batched inputs in modal mode
    if (event.request_type === 'inputs' && event.items && batchedInputsMode === 'modal') {
      setModalOpen(true);
    }
  }, [event.request_id, event.request_type, event.items, batchedInputsMode]);

  // Load preference for batched inputs mode
  React.useEffect(() => {
    const loadPreference = async () => {
      try {
        const response = await fetch('/api/config');
        if (response.ok) {
          const data = await response.json();
          const mode = data.config?.hitl?.batched_inputs_mode || 'inline';
          setBatchedInputsMode(mode);
        }
      } catch (error) {
        console.error('Failed to load batched inputs preference:', error);
      }
    };
    loadPreference();
  }, []);

  const handleResponse = (value: any) => {
    setResponded(true);
    setResponseValue(value);
    if (onRespond) {
      onRespond(event.request_id, value);
    }
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

          {/* Context section - runtime context shown in both modes, application context only in standalone */}
          {(event.runtime_context || (displayMode === 'standalone' && event.application_context)) && (
            <div className="rounded-md border border-border bg-muted/30 p-3 space-y-2 text-sm">
              {/* Runtime context */}
              {event.runtime_context && (
                <div className="space-y-1">
                  {/* Source location - show file even without line number */}
                  {(event.runtime_context.source_line || event.runtime_context.source_file) && (
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <FileCode className="h-4 w-4" />
                      <span>
                        {event.runtime_context.source_line && `Line ${event.runtime_context.source_line}`}
                        {event.runtime_context.source_line && event.runtime_context.source_file && ' in '}
                        {event.runtime_context.source_file}
                      </span>
                    </div>
                  )}
                  {/* Timing and position info */}
                  <div className="flex items-center gap-4 text-muted-foreground">
                    {event.runtime_context.elapsed_seconds > 0 && (
                      <div className="flex items-center gap-1">
                        <Clock className="h-4 w-4" />
                        <span>Running for {formatElapsedTime(event.runtime_context.elapsed_seconds)}</span>
                      </div>
                    )}
                    {event.runtime_context.checkpoint_position >= 0 && (
                      <div className="flex items-center gap-1">
                        <RotateCw className="h-4 w-4" />
                        <span>Checkpoint {event.runtime_context.checkpoint_position}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Application context - only in standalone mode */}
              {displayMode === 'standalone' && event.application_context && event.application_context.length > 0 && (
                <div className="space-y-1 pt-1 border-t border-border/50">
                  {event.application_context.map((link, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-muted-foreground">
                      <span className="font-medium text-foreground">{link.name}:</span>
                      {link.url ? (
                        <a
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline flex items-center gap-1"
                        >
                          {link.value}
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      ) : (
                        <span>{link.value}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Response section - Registry-based rendering */}
          {(() => {
            // Special handling for batched inputs - supports inline (default) or modal mode
            if (event.request_type === 'inputs' && event.items) {
              return (
                <>
                  <div className="text-sm text-foreground">
                    {event.message}
                  </div>

                  {responded ? (
                    <div className="space-y-2">
                      <div className="text-sm text-green-600 font-medium">
                        ✓ Response Submitted
                      </div>
                      <div className="text-xs text-muted-foreground space-y-1 pl-4 border-l-2 border-green-600/30">
                        {Object.entries(responseValue || {}).map(([key, value]) => {
                          const item = event.items?.find(i => i.item_id === key);
                          const label = item?.label || key;
                          const displayValue = Array.isArray(value)
                            ? value.join(', ')
                            : typeof value === 'boolean'
                            ? (value ? 'Yes' : 'No')
                            : String(value || '(empty)');
                          return (
                            <div key={key}>
                              <span className="font-medium">{label}:</span> {displayValue}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ) : batchedInputsMode === 'inline' ? (
                    // INLINE MODE (Default) - Render all items in the event stream
                    <HITLInputsPanel
                      request={{
                        request_id: event.request_id,
                        procedure_id: event.procedure_name,
                        procedure_name: event.procedure_name,
                        invocation_id: event.invocation_id,
                        request_type: event.request_type,
                        message: event.message,
                        default_value: event.default_value,
                        timeout_seconds: event.timeout_seconds,
                        options: event.options,
                        items: event.items,
                        subject: event.subject,
                        elapsed_seconds: event.runtime_context?.elapsed_seconds,
                        input_summary: event.input_summary,
                        conversation: event.conversation,
                        prior_interactions: event.prior_interactions,
                        metadata: event.metadata,
                      }}
                      onRespond={(response) => handleResponse(response.value)}
                      showHeader={false}
                      showContext={false}
                    />
                  ) : (
                    // MODAL MODE - Modal opens automatically
                    <>
                      <div className="flex items-center gap-2">
                        <div className="text-sm text-muted-foreground">
                          Multiple inputs requested ({event.items?.length || 0} items)
                        </div>
                        {!modalOpen && (
                          <Button
                            onClick={() => setModalOpen(true)}
                            variant="outline"
                            size="sm"
                          >
                            Reopen Form
                          </Button>
                        )}
                      </div>

                      <HITLInputsModal
                        open={modalOpen}
                        onOpenChange={setModalOpen}
                        title={event.message}
                        description="Please fill out all required fields."
                        request={{
                          request_id: event.request_id,
                          procedure_id: event.procedure_name,
                          procedure_name: event.procedure_name,
                          invocation_id: event.invocation_id,
                          request_type: event.request_type,
                          message: event.message,
                          default_value: event.default_value,
                          timeout_seconds: event.timeout_seconds,
                          options: event.options,
                          items: event.items,
                          subject: event.subject,
                          elapsed_seconds: event.runtime_context?.elapsed_seconds,
                          input_summary: event.input_summary,
                          conversation: event.conversation,
                          prior_interactions: event.prior_interactions,
                          metadata: event.metadata,
                        }}
                        onRespond={(response) => handleResponse(response.value)}
                        onCancel={() => setModalOpen(false)}
                        showHeader={false}
                        showContext={false}
                      />
                    </>
                  )}
                </>
              );
            }

            const componentType = event.metadata?.component_type;
            const useSharedComponents =
              !componentType &&
              ['approval', 'input', 'select', 'review', 'upload', 'escalation'].includes(
                event.request_type
              );

            if (useSharedComponents) {
              return (
                <>
                  {event.request_type !== 'approval' && (
                    <div className="text-sm text-foreground">
                      {event.message}
                    </div>
                  )}
                  <HITLRequestRenderer
                    request={{
                      request_id: event.request_id,
                      procedure_id: event.procedure_name,
                      procedure_name: event.procedure_name,
                      invocation_id: event.invocation_id,
                      request_type: event.request_type,
                      message: event.message,
                      default_value: event.default_value,
                      timeout_seconds: event.timeout_seconds,
                      options: event.options,
                      items: event.items,
                      subject: event.subject,
                      elapsed_seconds: event.runtime_context?.elapsed_seconds,
                      input_summary: event.input_summary,
                      conversation: event.conversation,
                      prior_interactions: event.prior_interactions,
                      metadata: event.metadata,
                    }}
                    onRespond={(response) => handleResponse(response.value)}
                    showHeader={false}
                    showContext={false}
                  />
                </>
              );
            }

            // For all other types, use registry-based rendering
            const ComponentRenderer = getComponentRenderer(event.request_type, componentType);

            if (!ComponentRenderer) {
              return (
                <>
                  <div className="text-sm text-foreground">
                    {event.message}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Unknown request type: {event.request_type}
                    {componentType && ` (component: ${componentType})`}
                  </div>
                </>
              );
            }

            return (
              <>
                {/* Message for non-approval types (approval has message in Confirmation component) */}
                {event.request_type !== 'approval' && (
                  <div className="text-sm text-foreground">
                    {event.message}
                  </div>
                )}

                {/* Response confirmation or component renderer */}
                {responded && event.request_type !== 'approval' ? (
                  <div className="text-sm text-green-600 font-medium">
                    ✓ Responded: {JSON.stringify(responseValue)}
                  </div>
                ) : (
                  <ComponentRenderer
                    item={{
                      item_id: event.request_id,
                      label: event.message,
                      request_type: event.request_type,
                      message: event.message,
                      options: event.options,
                      metadata: event.metadata,
                      required: true,
                    }}
                    value={responseValue}
                    onValueChange={handleResponse}
                    responded={responded}
                  />
                )}
              </>
            );
          })()}
        </div>
      </div>
    </BaseEventComponent>
  );
};
