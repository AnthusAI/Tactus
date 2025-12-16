import React from 'react';
import { ProcedureMetadata } from '@/types/metadata';
import { Loader2, FileQuestion } from 'lucide-react';
import { ParametersSection } from './metadata/ParametersSection';
import { OutputsSection } from './metadata/OutputsSection';
import { AgentsSection } from './metadata/AgentsSection';
import { ToolsSection } from './metadata/ToolsSection';
import { SpecificationsSection } from './metadata/SpecificationsSection';
import { StagesSection } from './metadata/StagesSection';
import { EvaluationsSection } from './metadata/EvaluationsSection';

interface ProcedureTabProps {
  metadata: ProcedureMetadata | null;
  loading: boolean;
}

export const ProcedureTab: React.FC<ProcedureTabProps> = ({ metadata, loading }) => {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">Loading metadata...</span>
        </div>
      </div>
    );
  }

  if (!metadata) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <FileQuestion className="h-8 w-8" />
          <span className="text-sm">No metadata available</span>
        </div>
      </div>
    );
  }

  const hasContent =
    metadata.description ||
    Object.keys(metadata.parameters).length > 0 ||
    Object.keys(metadata.outputs).length > 0 ||
    Object.keys(metadata.agents).length > 0 ||
    metadata.tools.length > 0 ||
    metadata.specifications !== null ||
    metadata.stages.length > 0 ||
    metadata.evaluations !== null;

  if (!hasContent) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <FileQuestion className="h-8 w-8" />
          <span className="text-sm">No metadata found</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full p-4 space-y-4 overflow-y-auto overflow-x-hidden">
      <ParametersSection parameters={metadata.parameters} />

      <OutputsSection outputs={metadata.outputs} />

      <StagesSection stages={metadata.stages} />

      <AgentsSection agents={metadata.agents} />

      <ToolsSection tools={metadata.tools} />

      <SpecificationsSection specifications={metadata.specifications} />

      <EvaluationsSection evaluations={metadata.evaluations} />

      {metadata.description && (
        <div>
          <h3 className="font-semibold text-sm mb-2">Description</h3>
          <p className="text-sm text-muted-foreground">{metadata.description}</p>
        </div>
      )}
    </div>
  );
};
