import React from 'react';
import { Wrench } from 'lucide-react';

interface ToolsSectionProps {
  tools: string[];
}

export const ToolsSection: React.FC<ToolsSectionProps> = ({ tools }) => {
  if (tools.length === 0) {
    return null;
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Wrench className="h-4 w-4" />
        <h3 className="font-semibold text-sm">Tools</h3>
      </div>
      <div className="flex flex-wrap gap-1">
        {tools.map((tool) => (
          <code key={tool} className="text-xs px-2 py-1 bg-muted rounded">
            {tool}
          </code>
        ))}
      </div>
    </div>
  );
};
