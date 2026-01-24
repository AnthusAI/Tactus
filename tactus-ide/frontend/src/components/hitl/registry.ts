/**
 * HITL Component Registry
 *
 * Provides a three-tier component registry system:
 * 1. Built-in components (backward compatibility for approval, input, select)
 * 2. Standard library (ships with Tactus - image-selector, text-options, etc.)
 * 3. Application components (registered at runtime by host applications)
 *
 * Priority order: Application > Standard > Built-in
 */

import { HITLComponentRenderer } from './types';
import { ApprovalComponent, InputComponent, SelectComponent } from './standard-library/builtin';
import { ImageSelectorComponent } from './standard-library/selectors';

/**
 * Tier 1: Built-in components (backward compatibility)
 *
 * These are the original HITL request types that existed before the unified
 * component architecture. They're mapped into the registry to maintain
 * backward compatibility while using the same rendering mechanism.
 */
const BUILTIN_COMPONENTS: Record<string, HITLComponentRenderer> = {
  'approval': ApprovalComponent,
  'input': InputComponent,
  'select': SelectComponent,
};

/**
 * Tier 2: Standard library (ships with Tactus)
 *
 * These are rich, reusable components that ship with Tactus and are available
 * to all applications. They use the same metadata-driven architecture as
 * custom components.
 */
const STANDARD_LIBRARY: Record<string, HITLComponentRenderer> = {
  'image-selector': ImageSelectorComponent,
  // More standard library components will be added here
  // 'text-options-selector': TextOptionsSelectorComponent,
};

/**
 * Tier 3: Application components (registered at runtime)
 *
 * Host applications can register their own custom components by calling
 * hitlRegistry.register(). These have highest priority and can even
 * override built-in or standard library components if needed.
 */
let applicationComponents: Record<string, HITLComponentRenderer> = {};

/**
 * Get the appropriate component renderer for a given request type and component type
 *
 * @param requestType - The HITL request type (approval, input, select, custom, etc.)
 * @param componentType - Optional component_type from metadata (for custom types)
 * @returns Component renderer or null if not found
 */
export function getComponentRenderer(
  requestType: string,
  componentType?: string
): HITLComponentRenderer | null {
  // Use component_type if provided (for custom types), otherwise use request_type (for built-ins)
  const key = componentType || requestType;

  // Priority order: Application > Standard > Built-in
  return (
    applicationComponents[key] ??
    STANDARD_LIBRARY[key] ??
    BUILTIN_COMPONENTS[key] ??
    null
  );
}

/**
 * Register a built-in component (internal use only)
 *
 * @param componentType - The component type identifier
 * @param renderer - The component renderer
 */
export function registerBuiltin(
  componentType: string,
  renderer: HITLComponentRenderer
): void {
  BUILTIN_COMPONENTS[componentType] = renderer;
}

/**
 * Register a standard library component (internal use only)
 *
 * @param componentType - The component type identifier
 * @param renderer - The component renderer
 */
export function registerStandardLibrary(
  componentType: string,
  renderer: HITLComponentRenderer
): void {
  STANDARD_LIBRARY[componentType] = renderer;
}

/**
 * Public registry API for host applications
 */
export const hitlRegistry = {
  /**
   * Register a custom component type
   *
   * @param componentType - Unique identifier for the component type
   * @param renderer - React component that implements HITLComponentRenderer interface
   *
   * @example
   * ```typescript
   * import { hitlRegistry } from '@tactus/frontend/hitl';
   * import MyCustomComponent from './MyCustomComponent';
   *
   * hitlRegistry.register('my-custom-type', MyCustomComponent);
   * ```
   */
  register(componentType: string, renderer: HITLComponentRenderer): void {
    if (applicationComponents[componentType]) {
      console.warn(
        `[HITL Registry] Overwriting existing component type: ${componentType}`
      );
    }
    applicationComponents[componentType] = renderer;
  },

  /**
   * Override a built-in or standard library component
   *
   * This is an alias for register() but makes the intent clear when you're
   * deliberately replacing a component that ships with Tactus.
   *
   * @param componentType - Component type to override
   * @param renderer - New component renderer
   *
   * @example
   * ```typescript
   * // Replace the built-in approval component with custom version
   * hitlRegistry.override('approval', CustomApprovalComponent);
   * ```
   */
  override(componentType: string, renderer: HITLComponentRenderer): void {
    this.register(componentType, renderer);
  },

  /**
   * Unregister a custom component type
   *
   * @param componentType - Component type to remove
   */
  unregister(componentType: string): void {
    delete applicationComponents[componentType];
  },

  /**
   * List all available component types
   *
   * @returns Object with arrays of built-in, standard, and application component types
   */
  listAvailable(): {
    builtin: string[];
    standard: string[];
    application: string[];
  } {
    return {
      builtin: Object.keys(BUILTIN_COMPONENTS),
      standard: Object.keys(STANDARD_LIBRARY),
      application: Object.keys(applicationComponents),
    };
  },

  /**
   * Clear all application-registered components (useful for testing)
   */
  clearApplicationComponents(): void {
    applicationComponents = {};
  },
};
