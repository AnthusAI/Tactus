/**
 * Utilities for synchronizing between GUI form state and YAML code.
 */

import * as yaml from 'js-yaml';

/**
 * Convert GUI object state to YAML string.
 *
 * @param obj - Configuration object from GUI
 * @returns YAML string representation
 */
export function syncGuiToCode(obj: Record<string, any>): string {
  // Return empty string for empty objects
  if (!obj || Object.keys(obj).length === 0) {
    return '';
  }

  return yaml.dump(obj, {
    indent: 2,
    lineWidth: -1, // Don't wrap lines
    noRefs: true, // Don't use anchors/references
    sortKeys: false, // Preserve key order
  });
}

/**
 * Convert YAML string to GUI object state.
 *
 * @param code - YAML string
 * @returns Configuration object for GUI
 * @throws {Error} If YAML is invalid
 */
export function syncCodeToGui(code: string): Record<string, any> {
  try {
    // Handle empty string
    if (!code.trim()) {
      return {};
    }

    const parsed = yaml.load(code);

    // Ensure we return an object
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      // If YAML is empty (just comments or whitespace), return empty object
      if (parsed === null) {
        return {};
      }
      throw new Error('YAML must represent an object');
    }

    return parsed as Record<string, any>;
  } catch (error) {
    if (error instanceof Error) {
      throw new Error(`Invalid YAML: ${error.message}`);
    }
    throw new Error('Invalid YAML');
  }
}

/**
 * Validate YAML syntax without parsing to object.
 *
 * @param code - YAML string to validate
 * @returns Error message if invalid, null if valid
 */
export function validateYaml(code: string): string | null {
  try {
    yaml.load(code);
    return null;
  } catch (error) {
    if (error instanceof Error) {
      return error.message;
    }
    return 'Unknown YAML error';
  }
}
