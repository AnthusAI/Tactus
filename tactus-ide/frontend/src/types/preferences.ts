/**
 * TypeScript type definitions for preferences feature.
 */

export type PreferencesMode = 'gui' | 'code';

export type ConfigSource =
  | 'cli'
  | 'sidecar'
  | 'local'
  | 'parent'
  | 'project'
  | 'user'
  | 'system'
  | 'environment';

export type FieldType =
  | 'string'
  | 'number'
  | 'boolean'
  | 'secret'
  | 'object'
  | 'array';

export interface CascadeInfo {
  effectiveConfig: Record<string, any>;
  sources: Record<string, ConfigSource>;
}

export interface ConfigResponse {
  config: Record<string, any>;
  project_config: Record<string, any>;
  user_config: Record<string, any>;
  cascade: Record<string, string>;
  project_config_path: string;
  user_config_path: string;
}

export interface PreferencesState {
  mode: PreferencesMode;
  guiValues: Record<string, any>;
  yamlCode: string;
  originalConfig: Record<string, any>;
  cascadeData: CascadeInfo;
  errors: string[];
  isDirty: boolean;
  isLoading: boolean;
}

export interface FieldProps {
  path: string[];
  value: any;
  onChange: (path: string[], newValue: any) => void;
  cascadeSource?: ConfigSource;
  error?: string;
}

export interface ValidationError {
  path: string;
  message: string;
}

export interface SaveConfigRequest {
  config: Record<string, any>;
  targetFile: 'project' | 'user';
  createBackup?: boolean;
}

export interface SaveConfigResponse {
  success: boolean;
  path: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

// Enhanced types for source tracking (Phase 2)

export interface ConfigSourceDetails {
  value: any;
  source: string;
  source_type: ConfigSource;
  path: string;
  overridden_by: string | null;
  override_chain: Array<[string, any]>;
  is_env_override: boolean;
  original_env_var: string | null;
}

export interface EnhancedConfigResponse {
  config: Record<string, any>;
  project_config: Record<string, any>;
  user_config: Record<string, any>;
  system_config: Record<string, any>;
  cascade: Record<string, string>;
  source_details: Record<string, ConfigSourceDetails>;
  writable_configs: {
    system: boolean;
    user: boolean;
    project: boolean;
  };
  config_paths: {
    system: string;
    user: string;
    project: string;
  };
  // Legacy fields for backward compatibility
  project_config_path: string;
  user_config_path: string;
}

export type ConfigSourceTarget = 'system' | 'user' | 'project' | 'combined';

export type SaveStrategy = 'source_aware' | 'force_user' | 'force_project';

export interface SaveBySourceRequest {
  changes: Record<string, any>;
  target_strategy: SaveStrategy;
}

export interface SaveBySourceResponse {
  success: boolean;
  saved_to: Record<string, string>;
  errors: string[];
}
