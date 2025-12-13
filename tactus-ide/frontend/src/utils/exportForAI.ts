/**
 * Export events in AI-comprehensible format (YAML).
 * 
 * This creates a structured export that includes all context needed
 * for an AI coding assistant to understand and debug issues.
 */

import { AnyEvent } from '@/types/events';

export function exportEventsForAI(events: AnyEvent[]): string {
  const timestamp = new Date().toISOString();
  
  // Determine operation type and status
  let operationType = 'unknown';
  let status = 'unknown';
  let filePath = '';
  
  // Extract key information from events
  const testStarted = events.find(e => e.event_type === 'test_started');
  const testCompleted = events.find(e => e.event_type === 'test_completed');
  const evalStarted = events.find(e => e.event_type === 'evaluation_started');
  const evalCompleted = events.find(e => e.event_type === 'evaluation_completed');
  const execution = events.find(e => e.event_type === 'execution');
  const validation = events.find(e => e.event_type === 'validation');
  
  if (testStarted || testCompleted) {
    operationType = 'test';
    status = (testCompleted as any)?.success ? 'passed' : 'failed';
    filePath = (testStarted as any)?.file || '';
  } else if (evalStarted || evalCompleted) {
    operationType = 'evaluate';
    status = 'completed';
    filePath = (evalStarted as any)?.file || '';
  } else if (execution) {
    operationType = 'run';
    status = (execution as any).lifecycle_stage === 'complete' ? 'success' : 'failed';
  } else if (validation) {
    operationType = 'validate';
    status = (validation as any).valid ? 'valid' : 'invalid';
  }
  
  // Build YAML output
  let yaml = `# Tactus IDE Results Export\n`;
  yaml += `# Generated: ${timestamp}\n`;
  yaml += `# Format: YAML (AI-comprehensible)\n\n`;
  
  yaml += `operation:\n`;
  yaml += `  type: ${operationType}\n`;
  yaml += `  status: ${status}\n`;
  yaml += `  file: "${filePath}"\n`;
  yaml += `  timestamp: "${timestamp}"\n\n`;
  
  // Export test results if available
  if (testCompleted) {
    const tc = testCompleted as any;
    // Results might be nested under 'result' key
    const result = tc.result || tc;
    const features = result.features || [];
    
    yaml += `test_results:\n`;
    yaml += `  total_scenarios: ${result.total_scenarios || 0}\n`;
    yaml += `  passed_scenarios: ${result.passed_scenarios || 0}\n`;
    yaml += `  failed_scenarios: ${result.failed_scenarios || 0}\n\n`;
    
    if (features.length > 0) {
      yaml += `  features:\n`;
      for (const feature of features) {
        yaml += `    - name: "${feature.name || 'Unknown'}"\n`;
        
        if (feature.scenarios && feature.scenarios.length > 0) {
          yaml += `      scenarios:\n`;
          for (const scenario of feature.scenarios) {
            yaml += `        - name: "${scenario.name}"\n`;
            yaml += `          status: ${scenario.status}\n`;
            yaml += `          duration: ${scenario.duration || 0}\n`;
            
            if (scenario.steps && scenario.steps.length > 0) {
              yaml += `          steps:\n`;
              for (const step of scenario.steps) {
                yaml += `            - keyword: "${step.keyword}"\n`;
                yaml += `              text: "${step.text}"\n`;
                yaml += `              status: ${step.status}\n`;
                if (step.error_message) {
                  yaml += `              error: "${escapeYaml(step.error_message)}"\n`;
                }
              }
            }
          }
        }
      }
      yaml += `\n`;
    }
  }
  
  // Export evaluation results if available
  if (evalCompleted) {
    const ec = evalCompleted as any;
    yaml += `evaluation_results:\n`;
    yaml += `  total_runs: ${ec.total_runs || 0}\n`;
    yaml += `  success_rate: ${ec.success_rate || 0}\n`;
    yaml += `  consistency_score: ${ec.consistency_score || 0}\n`;
    yaml += `  duration_seconds: ${ec.duration_seconds || 0}\n\n`;
    
    if (ec.scenario_results && ec.scenario_results.length > 0) {
      yaml += `  scenario_results:\n`;
      for (const sr of ec.scenario_results) {
        yaml += `    - name: "${sr.name}"\n`;
        yaml += `      success_rate: ${sr.success_rate}\n`;
        yaml += `      consistency: ${sr.consistency}\n`;
        yaml += `      is_flaky: ${sr.is_flaky}\n`;
      }
      yaml += `\n`;
    }
  }
  
  // Export validation results if available
  if (validation) {
    const v = validation as any;
    yaml += `validation_results:\n`;
    yaml += `  valid: ${v.valid}\n`;
    
    if (v.errors && v.errors.length > 0) {
      yaml += `  errors:\n`;
      for (const error of v.errors) {
        yaml += `    - "${escapeYaml(error)}"\n`;
      }
    }
    
    if (v.warnings && v.warnings.length > 0) {
      yaml += `  warnings:\n`;
      for (const warning of v.warnings) {
        yaml += `    - "${escapeYaml(warning)}"\n`;
      }
    }
    yaml += `\n`;
  }
  
  // Export execution result if available
  if (execution) {
    const ex = execution as any;
    yaml += `execution_result:\n`;
    yaml += `  stage: ${ex.lifecycle_stage}\n`;
    yaml += `  success: ${ex.success || false}\n`;
    if (ex.error) {
      yaml += `  error: "${escapeYaml(ex.error)}"\n`;
    }
    if (ex.result) {
      yaml += `  result: ${JSON.stringify(ex.result)}\n`;
    }
    yaml += `\n`;
  }
  
  // Export log events (condensed)
  const logEvents = events.filter(e => e.event_type === 'log');
  if (logEvents.length > 0) {
    yaml += `logs:\n`;
    yaml += `  total_count: ${logEvents.length}\n`;
    yaml += `  sample:\n`;
    // Show first 5 and last 5 logs
    const sampleLogs = [
      ...logEvents.slice(0, 5),
      ...logEvents.slice(-5)
    ];
    for (const log of sampleLogs) {
      const l = log as any;
      yaml += `    - level: ${l.level}\n`;
      yaml += `      message: "${escapeYaml(l.message)}"\n`;
      if (l.data) {
        yaml += `      data: ${JSON.stringify(l.data)}\n`;
      }
    }
    yaml += `\n`;
  }
  
  // Export all events for debugging (condensed)
  yaml += `all_events:\n`;
  yaml += `  total_count: ${events.length}\n`;
  yaml += `  event_types:\n`;
  const eventTypeCounts: Record<string, number> = {};
  for (const event of events) {
    eventTypeCounts[event.event_type] = (eventTypeCounts[event.event_type] || 0) + 1;
  }
  for (const [type, count] of Object.entries(eventTypeCounts)) {
    yaml += `    ${type}: ${count}\n`;
  }
  yaml += `  events:\n`;
  for (const event of events) {
    yaml += `    - type: ${event.event_type}\n`;
    yaml += `      timestamp: ${event.timestamp}\n`;
    // Include key fields based on event type
    if (event.event_type === 'test_completed') {
      const tc = event as any;
      yaml += `      success: ${tc.success}\n`;
      yaml += `      feature_name: "${tc.feature_name || ''}"\n`;
      yaml += `      scenarios_count: ${tc.scenarios?.length || 0}\n`;
    } else if (event.event_type === 'test_scenario_completed') {
      const tsc = event as any;
      yaml += `      scenario_name: "${tsc.name || ''}"\n`;
      yaml += `      status: ${tsc.status}\n`;
      yaml += `      steps_count: ${tsc.steps?.length || 0}\n`;
    } else if (event.event_type === 'execution') {
      const ex = event as any;
      yaml += `      stage: ${ex.lifecycle_stage}\n`;
      yaml += `      success: ${ex.success || false}\n`;
      if (ex.error) {
        yaml += `      error: "${escapeYaml(ex.error)}"\n`;
      }
    }
  }
  yaml += `\n`;
  
  // Add helpful context
  yaml += `# How to use this export:\n`;
  yaml += `# 1. Copy this entire YAML block\n`;
  yaml += `# 2. Paste it into your AI coding assistant\n`;
  yaml += `# 3. Ask for help debugging or understanding the issue\n`;
  yaml += `#\n`;
  yaml += `# The AI will have full context about:\n`;
  yaml += `# - What operation was performed\n`;
  yaml += `# - What succeeded and what failed\n`;
  yaml += `# - Detailed step-by-step results\n`;
  yaml += `# - Error messages and stack traces\n`;
  yaml += `# - Relevant log output\n`;
  
  return yaml;
}

function escapeYaml(str: string): string {
  return str
    .replace(/\\/g, '\\\\')
    .replace(/"/g, '\\"')
    .replace(/\n/g, '\\n')
    .replace(/\r/g, '\\r')
    .replace(/\t/g, '\\t');
}
