/**
 * Built-in Approval Component
 *
 * Renders an approval request using AI SDK Elements Confirmation component.
 * Supports custom options via metadata, or defaults to Approve/Reject buttons.
 */

import React from 'react';
import { Check, X } from 'lucide-react';
import {
  Confirmation,
  ConfirmationRequest,
  ConfirmationAccepted,
  ConfirmationRejected,
  ConfirmationActions,
  ConfirmationAction,
} from '@/components/ai-elements/confirmation';
import { HITLComponentRendererProps } from '../../types';

export const ApprovalComponent: React.FC<HITLComponentRendererProps> = ({
  item,
  value,
  onValueChange,
  responded,
}) => {
  return (
    <Confirmation
      approval={
        responded
          ? {
              id: item.item_id,
              approved: !!value,
              reason: value ? 'Approved by user' : 'Rejected by user',
            }
          : {
              id: item.item_id,
            }
      }
      state={
        responded
          ? ('approval-responded' as any)
          : ('approval-requested' as any)
      }
    >
      <ConfirmationRequest>{item.message}</ConfirmationRequest>

      <ConfirmationAccepted>
        <Check className="h-4 w-4" />
        <span>You approved this action</span>
      </ConfirmationAccepted>

      <ConfirmationRejected>
        <X className="h-4 w-4" />
        <span>You rejected this action</span>
      </ConfirmationRejected>

      <ConfirmationActions>
        {item.options && item.options.length > 0 ? (
          // Custom options provided
          item.options.map((option) => (
            <ConfirmationAction
              key={option.label}
              variant={option.style === 'danger' ? 'destructive' : 'default'}
              onClick={() => onValueChange(option.value)}
            >
              {option.label}
            </ConfirmationAction>
          ))
        ) : (
          // Default Approve/Reject buttons
          <>
            <ConfirmationAction
              variant="outline"
              onClick={() => onValueChange(false)}
            >
              <X className="h-4 w-4 mr-1" />
              Reject
            </ConfirmationAction>
            <ConfirmationAction
              variant="default"
              onClick={() => onValueChange(true)}
            >
              <Check className="h-4 w-4 mr-1" />
              Approve
            </ConfirmationAction>
          </>
        )}
      </ConfirmationActions>
    </Confirmation>
  );
};
