/**
 * SourceBadge - Visual indicator showing where a config value comes from.
 * Shows source type with Lucide icon and tooltip with full override chain.
 * When a value is overridden, shows multiple badges to indicate the chain.
 */

import React from 'react';
import { Badge } from '../ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../ui/tooltip';
import {
  AlertTriangle,
  Globe,
  User,
  FolderOpen,
  Settings,
  Folder,
  FileText,
  Link,
  HelpCircle,
  ArrowRight,
} from 'lucide-react';
import { ConfigSourceDetails } from '../../types/preferences';

// Map source types to Lucide icons and labels
// All variants use 'secondary' or 'outline' for proper light/dark mode contrast
const SOURCE_CONFIG = {
  environment: {
    Icon: Globe,
    label: 'env',
    variant: 'secondary' as const,
  },
  user: {
    Icon: User,
    label: 'user',
    variant: 'secondary' as const,
  },
  project: {
    Icon: FolderOpen,
    label: 'project',
    variant: 'secondary' as const,
  },
  system: {
    Icon: Settings,
    label: 'system',
    variant: 'outline' as const,
  },
  parent: {
    Icon: Folder,
    label: 'parent',
    variant: 'outline' as const,
  },
  local: {
    Icon: FileText,
    label: 'local',
    variant: 'outline' as const,
  },
  sidecar: {
    Icon: Link,
    label: 'sidecar',
    variant: 'outline' as const,
  },
};

const DEFAULT_CONFIG = {
  Icon: HelpCircle,
  label: 'unknown',
  variant: 'outline' as const,
};

interface SourceBadgeProps {
  sourceDetails?: ConfigSourceDetails;
  showOverrideChain?: boolean;
}

/**
 * Get the source config for a source type string
 */
function getSourceConfig(sourceType: string) {
  return SOURCE_CONFIG[sourceType as keyof typeof SOURCE_CONFIG] || DEFAULT_CONFIG;
}

/**
 * Extract source type from a source string like "project:/path/to/file"
 */
function extractSourceType(source: string): string {
  return source.split(':')[0];
}

/**
 * Single badge component for a source type
 */
function SingleBadge({
  sourceType,
  showWarning = false,
  className = '',
}: {
  sourceType: string;
  showWarning?: boolean;
  className?: string;
}) {
  const config = getSourceConfig(sourceType);
  const { Icon, label, variant } = config;

  return (
    <Badge variant={variant} className={`text-xs ${className}`}>
      <Icon className="h-3 w-3 mr-1" />
      {label}
      {showWarning && (
        <AlertTriangle className="ml-1 h-3 w-3 text-destructive" />
      )}
    </Badge>
  );
}

export function SourceBadge({
  sourceDetails,
  showOverrideChain = true,
}: SourceBadgeProps) {
  if (!sourceDetails) {
    return null;
  }

  const { source_type, is_env_override, original_env_var, override_chain } = sourceDetails;

  // Determine if we should show multiple badges
  // Show override chain if there's more than one entry and it involves different source types
  const hasOverride = override_chain && override_chain.length > 1;
  const showMultipleBadges = showOverrideChain && hasOverride;

  // Build tooltip content
  const tooltipContent = (
    <div className="space-y-2">
      <div className="font-medium flex items-center gap-2">
        {React.createElement(getSourceConfig(source_type).Icon, { className: 'h-4 w-4' })}
        <span>Source: {getSourceConfig(source_type).label}</span>
      </div>

      {is_env_override && original_env_var && (
        <div className="flex items-center gap-2 text-destructive">
          <AlertTriangle className="h-3 w-3" />
          <span className="text-xs">Overridden by environment variable</span>
        </div>
      )}

      {original_env_var && (
        <div className="text-xs text-muted-foreground">
          From: <code className="bg-muted px-1 py-0.5 rounded">{original_env_var}</code>
        </div>
      )}

      {override_chain && override_chain.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs font-medium">Override chain:</div>
          <div className="space-y-0.5">
            {override_chain.map(([source, value], index) => {
              const srcType = extractSourceType(source);
              const srcConfig = getSourceConfig(srcType);
              const SrcIcon = srcConfig.Icon;

              // Truncate long values, mask secrets
              let displayValue: string;
              if (typeof value === 'string') {
                if (value.length > 30) {
                  displayValue = `${value.substring(0, 10)}...${value.substring(value.length - 5)}`;
                } else {
                  displayValue = value;
                }
              } else {
                displayValue = JSON.stringify(value);
              }

              return (
                <div key={index} className="text-xs text-muted-foreground flex items-center gap-2">
                  <span className="opacity-50 w-4">{index + 1}.</span>
                  <SrcIcon className="h-3 w-3 flex-shrink-0" />
                  <span className="flex-shrink-0">{srcConfig.label}:</span>
                  <code className="bg-muted px-1 py-0.5 rounded truncate max-w-[150px]">
                    {displayValue}
                  </code>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );

  // If showing multiple badges for override chain
  if (showMultipleBadges && override_chain) {
    // Get unique source types from the chain (in order)
    const sourceTypes: string[] = [];
    for (const [source] of override_chain) {
      const srcType = extractSourceType(source);
      if (!sourceTypes.includes(srcType)) {
        sourceTypes.push(srcType);
      }
    }

    // Only show first and last if there are more than 2
    const displayTypes = sourceTypes.length > 2
      ? [sourceTypes[0], sourceTypes[sourceTypes.length - 1]]
      : sourceTypes;

    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex items-center gap-1 cursor-help">
              {displayTypes.map((srcType, index) => (
                <React.Fragment key={srcType}>
                  {index > 0 && (
                    <ArrowRight className="h-3 w-3 text-muted-foreground" />
                  )}
                  <SingleBadge
                    sourceType={srcType}
                    showWarning={index === displayTypes.length - 1 && is_env_override}
                  />
                </React.Fragment>
              ))}
            </div>
          </TooltipTrigger>
          <TooltipContent className="max-w-md">
            {tooltipContent}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  // Single badge (no override chain to show)
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="cursor-help">
            <SingleBadge
              sourceType={source_type}
              showWarning={is_env_override}
            />
          </div>
        </TooltipTrigger>
        <TooltipContent className="max-w-md">
          {tooltipContent}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
