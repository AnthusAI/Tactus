import React from 'react';

type HITLResponse = {
  value: unknown;
};

type HITLBaseProps = {
  onRespond?: (response: HITLResponse) => void;
};

export const HITLInputsPanel: React.FC<HITLBaseProps> = () => null;

export const HITLInputsModal: React.FC<HITLBaseProps & { open?: boolean }> = () => null;

export const HITLRequestRenderer: React.FC<HITLBaseProps> = () => null;
