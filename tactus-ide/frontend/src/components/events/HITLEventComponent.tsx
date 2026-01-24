import React, { useState } from 'react';
import { Bell, CheckCircle2, Check, X, FileCode, Clock, ExternalLink, RotateCw } from 'lucide-react';
import { BaseEventComponent } from './BaseEventComponent';
import { HITLRequestEvent } from '@/types/events';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../ui/tabs';
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
  const [formValues, setFormValues] = useState<Record<string, any>>({});
  const [batchedInputsMode, setBatchedInputsMode] = useState<'inline' | 'modal'>('inline');

  // Reset form values when a new event arrives
  React.useEffect(() => {
    setFormValues({});
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

  const handleFormSubmit = () => {
    handleResponse(formValues);
    setModalOpen(false);
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
              // Helper to render individual form items using registry components
              const renderFormItem = (item: typeof event.items[0]) => {
                const ComponentRenderer = getComponentRenderer(item.request_type, item.metadata?.component_type);

                if (ComponentRenderer) {
                  return (
                    <ComponentRenderer
                      item={item}
                      value={formValues[item.item_id]}
                      onValueChange={(value) => setFormValues(prev => ({ ...prev, [item.item_id]: value }))}
                      responded={false}
                    />
                  );
                }

                return <div className="text-sm text-muted-foreground">Unknown type: {item.request_type}</div>;
              };

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
                    <>
                      <div className="space-y-4 border rounded-md p-4 bg-muted/30" key={event.request_id}>
                        {event.items?.map((item, index) => (
                          <div key={`${event.request_id}-${item.item_id}`} className="space-y-2">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-medium text-muted-foreground">
                                {index + 1} of {event.items?.length || 0}
                              </span>
                              <Label className="text-sm font-semibold">{item.message}</Label>
                              {item.required && <span className="text-destructive text-xs">*</span>}
                            </div>
                            {renderFormItem(item)}
                          </div>
                        ))}
                      </div>
                      <Button
                        onClick={handleFormSubmit}
                        className="w-full"
                        disabled={event.items?.some(item => {
                          if (!item.required) return false;
                          const value = formValues[item.item_id];
                          // Check if value is missing or invalid
                          if (value === undefined || value === null) return true;
                          // For arrays (multi-select), check if empty
                          if (Array.isArray(value) && value.length === 0) return true;
                          // For strings, check if empty
                          if (typeof value === 'string' && value.trim() === '') return true;
                          return false;
                        })}
                      >
                        Submit All
                      </Button>
                    </>
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

                      {/* Batched Inputs Modal */}
                      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
                        <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
                          <DialogHeader>
                            <DialogTitle>Complete Form</DialogTitle>
                            <DialogDescription>
                              Please fill out all required fields
                            </DialogDescription>
                          </DialogHeader>

                          <Tabs defaultValue={event.items?.[0]?.item_id} className="flex-1 overflow-hidden flex flex-col">
                            <TabsList className="w-full justify-start overflow-x-auto flex-shrink-0">
                              {event.items?.map((item) => (
                                <TabsTrigger key={item.item_id} value={item.item_id} className="flex items-center gap-1">
                                  {item.label}
                                  {item.required && <span className="text-destructive">*</span>}
                                </TabsTrigger>
                              ))}
                            </TabsList>

                            <div className="flex-1 overflow-y-auto mt-4">
                              {event.items?.map((item) => (
                                <TabsContent key={item.item_id} value={item.item_id} className="space-y-4">
                                  <div>
                                    <Label className="text-base font-semibold">{item.message}</Label>
                                    {item.required && <span className="text-destructive ml-1">*</span>}
                                  </div>

                                  {/* Render input based on type */}
                                  {item.request_type === 'approval' && (
                                    <div className="space-y-2">
                                      <Button
                                        onClick={() => setFormValues(prev => ({ ...prev, [item.item_id]: true }))}
                                        variant={formValues[item.item_id] === true ? 'default' : 'outline'}
                                        className="w-full"
                                      >
                                        <Check className="h-4 w-4 mr-2" />
                                        Approve
                                      </Button>
                                      <Button
                                        onClick={() => setFormValues(prev => ({ ...prev, [item.item_id]: false }))}
                                        variant={formValues[item.item_id] === false ? 'default' : 'outline'}
                                        className="w-full"
                                      >
                                        <X className="h-4 w-4 mr-2" />
                                        Reject
                                      </Button>
                                    </div>
                                  )}

                                  {item.request_type === 'input' && (
                                    <input
                                      type="text"
                                      placeholder={item.metadata?.placeholder || 'Enter your response...'}
                                      className="w-full px-3 py-2 text-sm border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                                      defaultValue={item.default_value || ''}
                                      onChange={(e) => setFormValues(prev => ({ ...prev, [item.item_id]: e.target.value }))}
                                    />
                                  )}

                                  {item.request_type === 'select' && item.options && (
                                    <div className="grid grid-cols-2 gap-2">
                                      {item.options.map((option) => {
                                        const isMultiple = item.metadata?.mode === 'multiple';
                                        const currentValue = formValues[item.item_id];
                                        const isSelected = isMultiple
                                          ? Array.isArray(currentValue) && currentValue.includes(option.value)
                                          : currentValue === option.value;

                                        return (
                                          <Button
                                            key={option.value}
                                            onClick={() => {
                                              if (isMultiple) {
                                                // Multi-select: toggle value in array
                                                setFormValues(prev => {
                                                  const current = Array.isArray(prev[item.item_id]) ? prev[item.item_id] : [];
                                                  const newValue = current.includes(option.value)
                                                    ? current.filter((v: string) => v !== option.value)
                                                    : [...current, option.value];
                                                  return { ...prev, [item.item_id]: newValue };
                                                });
                                              } else {
                                                // Single select: set value
                                                setFormValues(prev => ({ ...prev, [item.item_id]: option.value }));
                                              }
                                            }}
                                            variant={isSelected ? 'default' : 'outline'}
                                            className="w-full"
                                          >
                                            {isMultiple && isSelected && <Check className="h-4 w-4 mr-2" />}
                                            {option.label}
                                          </Button>
                                        );
                                      })}
                                    </div>
                                  )}
                                </TabsContent>
                              ))}
                            </div>
                          </Tabs>

                          <DialogFooter>
                            <Button variant="outline" onClick={() => setModalOpen(false)}>
                              Cancel
                            </Button>
                            <Button onClick={handleFormSubmit}>
                              Submit All
                            </Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>
                    </>
                  )}
                </>
              );
            }

            // For all other types, use registry-based rendering
            const componentType = event.metadata?.component_type;
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
