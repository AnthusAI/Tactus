export interface ParameterDeclaration {
  name: string;
  type: string;
  required: boolean;
  default?: any;
  description?: string;
}

export interface OutputFieldDeclaration {
  name: string;
  type: string;
  required: boolean;
  description?: string;
}

export interface AgentDeclaration {
  name: string;
  provider: string;
  model: string;
  system_prompt: string;
  tools: string[];
}

export interface SpecificationsData {
  text: string;
  feature_name: string | null;
  scenario_count: number;
}

export interface EvaluationsData {
  dataset_count: number;
  evaluator_count: number;
  runs: number;
  parallel: boolean;
}

export interface ProcedureMetadata {
  description: string | null;
  parameters: Record<string, ParameterDeclaration>;
  outputs: Record<string, OutputFieldDeclaration>;
  agents: Record<string, AgentDeclaration>;
  toolsets: Record<string, any>;
  tools: string[];
  specifications: SpecificationsData | null;
  stages: string[];
  evaluations: EvaluationsData | null;
}
