import React, { useMemo, useState, useEffect } from 'react';
import {
  AnyEvent,
  TestStartedEvent,
  TestScenarioStartedEvent,
  TestScenarioCompletedEvent,
  TestCompletedEvent,
} from '@/types/events';
import { CollapsibleTestScenario } from './CollapsibleTestScenario';
import { TestCompletedEventComponent } from './TestEventComponent';
import { PlayCircle, CheckCircle, XCircle, Loader2 } from 'lucide-react';

interface TestProgressContainerProps {
  events: AnyEvent[];
}

type ScenarioStatus = 'pending' | 'running' | 'passed' | 'failed';

interface ScenarioState {
  name: string;
  status: ScenarioStatus;
  index: number;
  totalScenarios: number;
  result?: TestScenarioCompletedEvent;
}

/**
 * TestProgressContainer aggregates test events and renders a collapsible
 * list of scenarios with real-time progress tracking.
 *
 * Features:
 * - Auto-expands the currently running scenario
 * - Auto-collapses passed scenarios (keeps failed expanded)
 * - Shows progress indicator: "2/5 scenarios completed"
 */
export const TestProgressContainer: React.FC<TestProgressContainerProps> = ({ events }) => {
  const [expandedScenarios, setExpandedScenarios] = useState<Set<string>>(new Set());

  // Parse events to build scenario state
  const { scenarios, testStarted, testCompleted, totalScenarios, currentRunning } = useMemo(() => {
    const scenarioMap = new Map<string, ScenarioState>();
    let testStartedEvent: TestStartedEvent | undefined;
    let testCompletedEvent: TestCompletedEvent | undefined;
    let total = 0;
    let running: string | undefined;

    for (const event of events) {
      if (event.event_type === 'test_started') {
        testStartedEvent = event as TestStartedEvent;
        total = testStartedEvent.total_scenarios;
      } else if (event.event_type === 'test_scenario_started') {
        const started = event as TestScenarioStartedEvent;
        scenarioMap.set(started.scenario_name, {
          name: started.scenario_name,
          status: 'running',
          index: started.scenario_index,
          totalScenarios: started.total_scenarios,
        });
        running = started.scenario_name;
        if (total === 0) total = started.total_scenarios;
      } else if (event.event_type === 'test_scenario_completed') {
        const completed = event as TestScenarioCompletedEvent;
        const existing = scenarioMap.get(completed.scenario_name);
        scenarioMap.set(completed.scenario_name, {
          name: completed.scenario_name,
          status: completed.status === 'passed' ? 'passed' : 'failed',
          index: existing?.index ?? 0,
          totalScenarios: existing?.totalScenarios ?? total,
          result: completed,
        });
        // Clear running if this was the running one
        if (running === completed.scenario_name) {
          running = undefined;
        }
      } else if (event.event_type === 'test_completed') {
        testCompletedEvent = event as TestCompletedEvent;
      }
    }

    // Sort scenarios by index
    const sortedScenarios = Array.from(scenarioMap.values()).sort((a, b) => a.index - b.index);

    return {
      scenarios: sortedScenarios,
      testStarted: testStartedEvent,
      testCompleted: testCompletedEvent,
      totalScenarios: total,
      currentRunning: running,
    };
  }, [events]);

  // Auto-expand logic: expand running scenario, keep failed expanded
  useEffect(() => {
    setExpandedScenarios((prev) => {
      const next = new Set(prev);

      for (const scenario of scenarios) {
        if (scenario.status === 'running') {
          // Always expand running
          next.add(scenario.name);
        } else if (scenario.status === 'failed') {
          // Keep failed expanded
          next.add(scenario.name);
        } else if (scenario.status === 'passed') {
          // Auto-collapse passed (unless user manually expanded)
          // Only auto-collapse if it was just running (transition)
          if (prev.has(scenario.name) && !prev.has(`manual_${scenario.name}`)) {
            next.delete(scenario.name);
          }
        }
      }

      return next;
    });
  }, [scenarios]);

  const toggleScenario = (name: string) => {
    setExpandedScenarios((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
        next.delete(`manual_${name}`);
      } else {
        next.add(name);
        next.add(`manual_${name}`); // Mark as manually toggled
      }
      return next;
    });
  };

  // Calculate progress
  const completedCount = scenarios.filter((s) => s.status === 'passed' || s.status === 'failed').length;
  const passedCount = scenarios.filter((s) => s.status === 'passed').length;
  const failedCount = scenarios.filter((s) => s.status === 'failed').length;
  const isRunning = currentRunning !== undefined || (completedCount < totalScenarios && totalScenarios > 0);

  // If test completed, show final summary
  if (testCompleted) {
    return (
      <div className="border border-border/50 rounded-md overflow-hidden">
        {/* Header */}
        <div className="px-3 py-2 bg-muted/30 border-b border-border/30 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {testCompleted.result.failed_scenarios === 0 ? (
              <CheckCircle className="h-4 w-4 text-green-500" />
            ) : (
              <XCircle className="h-4 w-4 text-red-500" />
            )}
            <span className="text-sm font-medium">
              Test Results: {passedCount} passed, {failedCount} failed
            </span>
          </div>
        </div>

        {/* Scenarios */}
        {scenarios.map((scenario) => (
          <CollapsibleTestScenario
            key={scenario.name}
            scenarioName={scenario.name}
            status={scenario.status}
            scenarioIndex={scenario.index}
            totalScenarios={totalScenarios}
            result={scenario.result}
            isExpanded={expandedScenarios.has(scenario.name)}
            onToggle={() => toggleScenario(scenario.name)}
          />
        ))}
      </div>
    );
  }

  // In-progress view
  return (
    <div className="border border-border/50 rounded-md overflow-hidden">
      {/* Header with progress */}
      <div className="px-3 py-2 bg-muted/30 border-b border-border/30 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isRunning ? (
            <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
          ) : (
            <PlayCircle className="h-4 w-4 text-muted-foreground" />
          )}
          <span className="text-sm font-medium">
            Running Tests
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {totalScenarios > 0 && (
            <span>
              {completedCount}/{totalScenarios} completed
            </span>
          )}
          {passedCount > 0 && (
            <span className="text-green-500">{passedCount} passed</span>
          )}
          {failedCount > 0 && (
            <span className="text-red-500">{failedCount} failed</span>
          )}
        </div>
      </div>

      {/* Scenarios */}
      {scenarios.length === 0 && totalScenarios > 0 && (
        <div className="px-3 py-4 text-sm text-muted-foreground text-center">
          Preparing scenarios...
        </div>
      )}

      {scenarios.map((scenario) => (
        <CollapsibleTestScenario
          key={scenario.name}
          scenarioName={scenario.name}
          status={scenario.status}
          scenarioIndex={scenario.index}
          totalScenarios={totalScenarios}
          result={scenario.result}
          isExpanded={expandedScenarios.has(scenario.name)}
          onToggle={() => toggleScenario(scenario.name)}
        />
      ))}
    </div>
  );
};

/**
 * Check if an events array contains test events that should be grouped.
 */
export function hasTestEvents(events: AnyEvent[]): boolean {
  return events.some(
    (e) =>
      e.event_type === 'test_started' ||
      e.event_type === 'test_scenario_started' ||
      e.event_type === 'test_scenario_completed' ||
      e.event_type === 'test_completed'
  );
}

/**
 * Extract test events from an events array.
 */
export function extractTestEvents(events: AnyEvent[]): AnyEvent[] {
  return events.filter(
    (e) =>
      e.event_type === 'test_started' ||
      e.event_type === 'test_scenario_started' ||
      e.event_type === 'test_scenario_completed' ||
      e.event_type === 'test_completed'
  );
}

/**
 * Get non-test events from an events array.
 */
export function getNonTestEvents(events: AnyEvent[]): AnyEvent[] {
  return events.filter(
    (e) =>
      e.event_type !== 'test_started' &&
      e.event_type !== 'test_scenario_started' &&
      e.event_type !== 'test_scenario_completed' &&
      e.event_type !== 'test_completed'
  );
}
