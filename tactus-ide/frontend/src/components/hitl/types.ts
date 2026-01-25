/**
 * Shared types for HITL component system
 */

import { HITLRequestItem } from '@/types/events';

/**
 * Props interface for all HITL component renderers
 */
export interface HITLComponentRendererProps {
  item: HITLRequestItem;
  value: any;
  onValueChange: (value: any) => void;
  responded: boolean;
}

/**
 * Component renderer signature for HITL components
 */
export type HITLComponentRenderer = React.FC<HITLComponentRendererProps>;
