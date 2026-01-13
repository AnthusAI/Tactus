/**
 * ConfigFieldView - Displays configuration fields with source badges.
 * A simpler alternative to full dynamic form generation for Phase 2D.
 */

import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { SourceBadge } from './SourceBadge';
import { ConfigSourceDetails } from '../../types/preferences';
import { Input } from '../ui/input';
import { Label } from '../ui/label';

/**
 * Detect AWS configuration conflicts.
 * Environment variables for credentials (access_key_id/secret_access_key) will override
 * the AWS profile setting, which can lead to confusion.
 */
function detectAwsConflict(
  config: Record<string, any>,
  sourceDetails: Record<string, ConfigSourceDetails>
): {
  hasConflict: boolean;
  message: string;
} {
  const aws = config?.aws;
  if (!aws) {
    return { hasConflict: false, message: '' };
  }

  const hasProfile = !!aws.profile;
  const hasCredentials = !!(aws.access_key_id || aws.secret_access_key);

  if (!hasProfile || !hasCredentials) {
    return { hasConflict: false, message: '' };
  }

  // Check if credentials come from environment (higher priority than profile)
  const accessKeySource = sourceDetails['aws.access_key_id'];
  const secretKeySource = sourceDetails['aws.secret_access_key'];
  const profileSource = sourceDetails['aws.profile'];

  const credentialsFromEnv =
    accessKeySource?.is_env_override || secretKeySource?.is_env_override;
  const profileFromEnv = profileSource?.is_env_override;

  // Warn if credentials from env will override a profile from config file
  if (credentialsFromEnv && !profileFromEnv) {
    return {
      hasConflict: true,
      message:
        'AWS credentials from environment variables will override the profile setting. ' +
        'The explicit credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) take precedence.',
    };
  }

  // Warn if both are set from different sources
  if (hasProfile && hasCredentials) {
    return {
      hasConflict: true,
      message:
        'Both AWS profile and explicit credentials are configured. ' +
        'Explicit credentials typically take precedence over profile. ' +
        'Consider using only one authentication method to avoid confusion.',
    };
  }

  return { hasConflict: false, message: '' };
}

interface ConfigFieldViewProps {
  config: Record<string, any>;
  sourceDetails: Record<string, ConfigSourceDetails>;
  onChange?: (path: string, value: any) => void;
  readOnly?: boolean;
}

export function ConfigFieldView({
  config,
  sourceDetails,
  onChange,
  readOnly = false,
}: ConfigFieldViewProps) {
  const renderValue = (
    path: string,
    value: any,
    depth: number = 0
  ): React.ReactNode => {
    const source = sourceDetails[path];
    const indentClass = depth > 0 ? `ml-${depth * 4}` : '';

    // Handle nested objects
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      // Check for AWS conflict when rendering the AWS section
      const awsConflict = path === 'aws' ? detectAwsConflict(config, sourceDetails) : { hasConflict: false, message: '' };

      return (
        <div key={path} className={`space-y-3 ${indentClass}`}>
          <div className="flex items-center justify-between gap-2 py-2 border-b">
            <h3 className="font-medium text-sm">{path.split('.').pop()}</h3>
            {source && <SourceBadge sourceDetails={source} />}
          </div>
          {awsConflict.hasConflict && (
            <div className="flex items-start gap-2 p-3 rounded-md bg-muted border border-border">
              <AlertTriangle className="h-4 w-4 text-destructive flex-shrink-0 mt-0.5" />
              <p className="text-xs text-foreground">
                {awsConflict.message}
              </p>
            </div>
          )}
          <div className="pl-4 space-y-3">
            {Object.entries(value).map(([key, val]) =>
              renderValue(`${path}.${key}`, val, depth + 1)
            )}
          </div>
        </div>
      );
    }

    // Handle arrays
    if (Array.isArray(value)) {
      return (
        <div key={path} className={`space-y-2 ${indentClass}`}>
          <div className="flex items-center justify-between gap-2">
            <Label className="text-sm">{path.split('.').pop()}</Label>
            {source && <SourceBadge sourceDetails={source} />}
          </div>
          <div className="pl-4 space-y-1">
            {value.map((item, index) => (
              <div key={index} className="text-sm text-muted-foreground">
                • {typeof item === 'object' ? JSON.stringify(item) : String(item)}
              </div>
            ))}
          </div>
        </div>
      );
    }

    // Handle primitive values (string, number, boolean, null)
    const fieldId = `field-${path}`;
    const isSecret = /key|secret|password|token|credential|auth/i.test(path);
    const isEnvOverride = source?.is_env_override || false;

    return (
      <div key={path} className={`space-y-2 ${indentClass}`}>
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor={fieldId} className="text-sm">
            {path.split('.').pop()}
          </Label>
          {source && <SourceBadge sourceDetails={source} />}
        </div>
        <Input
          id={fieldId}
          type={isSecret ? 'password' : 'text'}
          value={value === null ? '' : String(value)}
          onChange={(e) => onChange?.(path, e.target.value)}
          readOnly={readOnly || isEnvOverride}
          disabled={isEnvOverride}
          className={`font-mono text-sm ${isSecret ? 'tracking-wider' : ''}`}
        />
        {isEnvOverride && (
          <p className="text-xs text-muted-foreground">
            This value is set by environment variable: {source?.original_env_var}
          </p>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {Object.entries(config).map(([key, value]) =>
        renderValue(key, value, 0)
      )}
    </div>
  );
}
