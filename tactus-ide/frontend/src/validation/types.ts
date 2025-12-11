/**
 * Type definitions for Tactus DSL validation.
 */

export type ValidationMode = 'quick' | 'full';

export type ParameterType = 'string' | 'number' | 'boolean' | 'array' | 'object';

export interface ValidationMessage {
  level: 'error' | 'warning';
  message: string;
  location?: [number, number];  // [line, column]
  declaration?: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationMessage[];
  warnings: ValidationMessage[];
  registry: ProcedureRegistry | null;
}

export interface ParameterDeclaration {
  name: string;
  parameterType: ParameterType;
  required: boolean;
  default?: any;
  description?: string;
  enum?: string[];
}

export interface OutputFieldDeclaration {
  name: string;
  fieldType: ParameterType;
  required: boolean;
  description?: string;
}

export interface SessionConfiguration {
  source: string;  // "own", "shared", or agent name
  filter?: any;
}

export interface AgentOutputSchema {
  fields: Record<string, OutputFieldDeclaration>;
}

export interface AgentDeclaration {
  name: string;
  provider?: string;
  model: string | Record<string, any>;
  systemPrompt: string | any;
  initialMessage?: string;
  tools: string[];
  output?: AgentOutputSchema;
  session?: SessionConfiguration;
  maxTurns: number;
}

export interface HITLDeclaration {
  name: string;
  hitlType: string;  // approval, input, review
  message: string;
  timeout?: number;
  default?: any;
  options?: Array<Record<string, any>>;
}

export interface ScenarioDeclaration {
  name: string;
  given: Record<string, any>;
  when?: string;
  thenOutput?: Record<string, any>;
  thenState?: Record<string, any>;
  mocks: Record<string, any>;
}

export interface SpecificationDeclaration {
  name: string;
  scenarios: ScenarioDeclaration[];
}

export interface ProcedureRegistry {
  // Metadata
  procedureName?: string;
  version?: string;
  description?: string;
  
  // Declarations
  parameters: Record<string, ParameterDeclaration>;
  outputs: Record<string, OutputFieldDeclaration>;
  agents: Record<string, AgentDeclaration>;
  hitlPoints: Record<string, HITLDeclaration>;
  stages: string[];
  specifications: SpecificationDeclaration[];
  
  // Prompts
  prompts: Record<string, string>;
  returnPrompt?: string;
  errorPrompt?: string;
  statusPrompt?: string;
  
  // Execution settings
  asyncEnabled: boolean;
  maxDepth: number;
  maxTurns: number;
  defaultProvider?: string;
  defaultModel?: string;
  
  // The procedure function (placeholder for TypeScript)
  procedureFunction?: any;
  
  // Source locations for error messages
  sourceLocations: Record<string, [number, number]>;
}
