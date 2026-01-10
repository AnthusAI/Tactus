import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { TestTube, Play, X, Settings2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const STORAGE_KEY = 'tactus-test-options';

export interface TestOptions {
  scenario: string | null;  // null = run all scenarios
  mockEnabled: boolean;
}

interface TestOptionsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  scenarios: string[];  // List of available scenario names
  onSubmit: (options: TestOptions) => void;
  onCancel: () => void;
}

// Load saved options from localStorage
function loadSavedOptions(): TestOptions {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      return {
        scenario: parsed.scenario ?? null,
        mockEnabled: parsed.mockEnabled ?? false,
      };
    }
  } catch {
    // Ignore parse errors
  }
  // Default: run all scenarios, mocks disabled (real API calls)
  return { scenario: null, mockEnabled: false };
}

// Save options to localStorage
function saveOptions(options: TestOptions) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(options));
  } catch {
    // Ignore storage errors
  }
}

export const TestOptionsModal: React.FC<TestOptionsModalProps> = ({
  open,
  onOpenChange,
  scenarios,
  onSubmit,
  onCancel,
}) => {
  const [options, setOptions] = useState<TestOptions>(loadSavedOptions);

  // Reset scenario selection if it's not in the available list
  useEffect(() => {
    if (options.scenario && !scenarios.includes(options.scenario)) {
      setOptions(prev => ({ ...prev, scenario: null }));
    }
  }, [scenarios, options.scenario]);

  // Save options when they change
  useEffect(() => {
    saveOptions(options);
  }, [options]);

  const handleScenarioChange = (value: string) => {
    setOptions(prev => ({
      ...prev,
      scenario: value === 'all' ? null : value,
    }));
  };

  const handleMockToggle = () => {
    setOptions(prev => ({
      ...prev,
      mockEnabled: !prev.mockEnabled,
    }));
  };

  const handleSubmit = () => {
    onSubmit(options);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]" onKeyDown={handleKeyDown}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <TestTube className="h-5 w-5" />
            Test Options
          </DialogTitle>
          <DialogDescription>
            Configure how to run the BDD tests.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Scenario Selection */}
          <div className="space-y-2">
            <label className="text-sm font-medium flex items-center gap-2">
              <Settings2 className="h-4 w-4 text-muted-foreground" />
              Run Scenarios
            </label>
            <select
              value={options.scenario ?? 'all'}
              onChange={(e) => handleScenarioChange(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <option value="all">All scenarios ({scenarios.length})</option>
              {scenarios.map((scenario) => (
                <option key={scenario} value={scenario}>
                  {scenario}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              Choose to run all scenarios or a specific one.
            </p>
          </div>

          {/* Mock Toggle */}
          <div className="space-y-2">
            <label className="text-sm font-medium flex items-center gap-2">
              Enable Mocks (CI Mode)
            </label>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleMockToggle}
                className={cn(
                  'relative h-6 w-11 rounded-full transition-colors',
                  options.mockEnabled ? 'bg-primary' : 'bg-muted'
                )}
              >
                <span
                  className={cn(
                    'absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-background transition-transform',
                    options.mockEnabled && 'translate-x-5'
                  )}
                />
              </button>
              <span className="text-sm text-muted-foreground">
                {options.mockEnabled ? 'Mocks enabled' : 'Real API calls'}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              {options.mockEnabled
                ? 'Using mocked responses. Agent behavior is configured via Mocks {} in the .tac file.'
                : 'Tests will make real LLM API calls. Requires API keys to be configured.'}
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            <X className="h-4 w-4 mr-2" />
            Cancel
          </Button>
          <Button onClick={handleSubmit}>
            <Play className="h-4 w-4 mr-2" />
            Run Tests
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
