/**
 * Preferences View - Main component for editing configuration.
 *
 * PLACEHOLDER: This is a basic implementation to get the UI working.
 * Full implementation with all field components coming next.
 */

import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import { Switch } from './ui/switch';
import { Label } from './ui/label';
import { X } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import {
  PreferencesMode,
  EnhancedConfigResponse,
  ConfigSourceTarget,
  ConfigSourceDetails,
} from '../types/preferences';
import { YamlCodeEditor } from './preferences/YamlCodeEditor';
import { ConfigFieldView } from './preferences/ConfigFieldView';
import { syncGuiToCode, syncCodeToGui } from '../utils/yamlSync';

interface PreferencesViewProps {
  onClose: () => void;
  onSave?: (config: Record<string, any>) => void;
}

export function PreferencesView({ onClose, onSave }: PreferencesViewProps) {
  const [mode, setMode] = useState<PreferencesMode>('gui');
  const [guiValues, setGuiValues] = useState<Record<string, any>>({});
  const [yamlCode, setYamlCode] = useState<string>('');
  const [originalConfig, setOriginalConfig] = useState<Record<string, any>>({});
  const [isDirty, setIsDirty] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [errors, setErrors] = useState<string[]>([]);

  // Source tracking state
  const [configSource, setConfigSource] = useState<ConfigSourceTarget>('project');
  const [sourceDetails, setSourceDetails] = useState<Record<string, ConfigSourceDetails>>({});
  const [projectConfig, setProjectConfig] = useState<Record<string, any>>({});
  const [userConfig, setUserConfig] = useState<Record<string, any>>({});
  const [systemConfig, setSystemConfig] = useState<Record<string, any>>({});
  const [effectiveConfig, setEffectiveConfig] = useState<Record<string, any>>({});

  // Load config on mount
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const response = await fetch('/api/config');
        if (!response.ok) {
          throw new Error('Failed to load config');
        }
        const data: EnhancedConfigResponse = await response.json();

        // Store all config levels
        setProjectConfig(data.project_config);
        setUserConfig(data.user_config);
        setSystemConfig(data.system_config);
        setEffectiveConfig(data.config);
        setSourceDetails(data.source_details);

        // GUI mode shows effective merged config (with env var overrides)
        // This allows users to see the actual values being used
        setGuiValues(data.config);
        // Code mode starts with project config for editing
        setYamlCode(syncGuiToCode(data.project_config));
        setOriginalConfig(data.project_config);
        setIsLoading(false);
      } catch (error) {
        console.error('Error loading config:', error);
        setErrors(['Failed to load configuration']);
        setIsLoading(false);
      }
    };

    loadConfig();
  }, []);

  // Update YAML when source selection changes
  useEffect(() => {
    if (mode !== 'code') return;

    let configToShow: Record<string, any>;
    switch (configSource) {
      case 'system':
        configToShow = systemConfig;
        break;
      case 'user':
        configToShow = userConfig;
        break;
      case 'project':
        configToShow = projectConfig;
        break;
      case 'combined':
        configToShow = effectiveConfig;
        break;
      default:
        configToShow = projectConfig;
    }

    setYamlCode(syncGuiToCode(configToShow));
  }, [configSource, mode, systemConfig, userConfig, projectConfig, effectiveConfig]);

  // Track dirty state
  useEffect(() => {
    try {
      const currentConfig = mode === 'gui' ? guiValues : (yamlCode.trim() ? syncCodeToGui(yamlCode) : {});
      setIsDirty(JSON.stringify(currentConfig) !== JSON.stringify(originalConfig));
    } catch (error) {
      // If YAML is invalid, just consider it dirty
      setIsDirty(true);
    }
  }, [guiValues, yamlCode, originalConfig, mode]);

  const handleModeChange = (newMode: PreferencesMode) => {
    if (newMode === 'code' && mode === 'gui') {
      // Sync GUI -> Code
      setYamlCode(syncGuiToCode(guiValues));
    } else if (newMode === 'gui' && mode === 'code') {
      // Sync Code -> GUI
      try {
        const parsed = syncCodeToGui(yamlCode);
        setGuiValues(parsed);
        setErrors([]);
      } catch (error) {
        setErrors([error instanceof Error ? error.message : 'Invalid YAML']);
        return; // Don't switch modes if invalid
      }
    }
    setMode(newMode);
  };

  const handleGuiFieldChange = (path: string, value: any) => {
    const keys = path.split('.');
    const newGuiValues = { ...guiValues };

    let current: any = newGuiValues;
    for (let i = 0; i < keys.length - 1; i++) {
      if (!current[keys[i]]) {
        current[keys[i]] = {};
      }
      current = current[keys[i]];
    }
    current[keys[keys.length - 1]] = value;

    setGuiValues(newGuiValues);
  };

  const handleSave = async () => {
    try {
      const configToSave = mode === 'gui' ? guiValues : syncCodeToGui(yamlCode);

      const response = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config: configToSave,
          targetFile: 'project',
          createBackup: true,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to save config');
      }

      setOriginalConfig(configToSave);
      setIsDirty(false);

      if (onSave) {
        onSave(configToSave);
      }

      // Show success feedback (could add toast here)
      console.log('Config saved successfully');
    } catch (error) {
      console.error('Error saving config:', error);
      setErrors(['Failed to save configuration']);
    }
  };

  const handleCancel = () => {
    if (isDirty) {
      if (confirm('You have unsaved changes. Are you sure you want to close?')) {
        onClose();
      }
    } else {
      onClose();
    }
  };

  if (isLoading) {
    return (
      <div className="fixed inset-0 z-50 bg-background flex items-center justify-center">
        <div className="text-muted-foreground">Loading configuration...</div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-background flex flex-col">
      {/* Header */}
      <div className="border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold">Preferences</h2>
          <div className="flex items-center gap-2">
            <Label htmlFor="show-code" className="text-sm">Show code</Label>
            <Switch
              id="show-code"
              checked={mode === 'code'}
              onCheckedChange={(checked) => handleModeChange(checked ? 'code' : 'gui')}
            />
          </div>
          {mode === 'code' && (
            <div className="flex items-center gap-2">
              <Label htmlFor="config-source" className="text-sm">View:</Label>
              <Select
                value={configSource}
                onValueChange={(value) => setConfigSource(value as ConfigSourceTarget)}
              >
                <SelectTrigger id="config-source" className="w-[180px] h-8">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="combined">Combined</SelectItem>
                  <SelectItem value="system">System</SelectItem>
                  <SelectItem value="user">User</SelectItem>
                  <SelectItem value="project">Project</SelectItem>
                </SelectContent>
              </Select>
              {(configSource === 'combined' || configSource === 'system') && (
                <span className="text-xs text-muted-foreground">(read-only)</span>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={
              !isDirty ||
              errors.length > 0 ||
              (mode === 'code' && (configSource === 'combined' || configSource === 'system'))
            }
          >
            Save Changes
          </Button>
          <Button variant="ghost" size="icon" onClick={handleCancel}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {mode === 'gui' ? (
          <ScrollArea className="h-full px-6 py-4">
            <div className="max-w-3xl mx-auto">
              <ConfigFieldView
                config={guiValues}
                sourceDetails={sourceDetails}
                onChange={handleGuiFieldChange}
                readOnly={false}
              />
            </div>
          </ScrollArea>
        ) : (
          <div className="h-full">
            <YamlCodeEditor
              value={yamlCode}
              onChange={setYamlCode}
              errors={errors}
              readOnly={configSource === 'combined' || configSource === 'system'}
            />
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t bg-muted/30 px-6 py-2 text-xs text-muted-foreground">
        {mode === 'code' ? (
          <>
            {configSource === 'combined' && 'Viewing: Combined configuration (effective values)'}
            {configSource === 'system' && 'Viewing: /etc/tactus/config.yml (read-only)'}
            {configSource === 'user' && `Editing: ~/.tactus/config.yml ${isDirty ? '(modified)' : ''}`}
            {configSource === 'project' && `Editing: .tactus/config.yml ${isDirty ? '(modified)' : ''}`}
          </>
        ) : (
          <>Editing: .tactus/config.yml {isDirty && '(modified)'}</>
        )}
      </div>
    </div>
  );
}
