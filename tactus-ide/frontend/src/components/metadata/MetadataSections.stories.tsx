import type { Meta, StoryObj } from '@storybook/react';
import { ParametersSection } from './ParametersSection';
import { OutputsSection } from './OutputsSection';
import { StagesSection } from './StagesSection';
import { AgentsSection } from './AgentsSection';
import { ToolsSection } from './ToolsSection';
import { SpecificationsSection } from './SpecificationsSection';
import { EvaluationsSection } from './EvaluationsSection';

// ============================================================================
// Parameters Section
// ============================================================================

const parametersMeta: Meta<typeof ParametersSection> = {
  title: 'Sidebar/Metadata/ParametersSection',
  component: ParametersSection,
  parameters: {
    layout: 'padded',
  },
};

export default parametersMeta;

type ParametersStory = StoryObj<typeof ParametersSection>;

export const ParametersWithMultipleTypes: ParametersStory = {
  args: {
    parameters: {
      user_input: {
        name: 'user_input',
        type: 'string',
        required: true,
        description: 'The user\'s input text to process',
      },
      max_iterations: {
        name: 'max_iterations',
        type: 'number',
        required: false,
        default: 5,
        description: 'Maximum number of iterations',
      },
      enable_debug: {
        name: 'enable_debug',
        type: 'boolean',
        required: false,
        default: false,
        description: 'Enable debug mode',
      },
    },
  },
};

export const ParametersWithDefaults: ParametersStory = {
  args: {
    parameters: {
      temperature: {
        name: 'temperature',
        type: 'number',
        required: false,
        default: 0.7,
        description: 'LLM temperature setting',
      },
      model: {
        name: 'model',
        type: 'string',
        required: false,
        default: 'gpt-4o',
        description: 'Model to use',
      },
    },
  },
};

export const ParametersRequiredOnly: ParametersStory = {
  args: {
    parameters: {
      api_key: {
        name: 'api_key',
        type: 'string',
        required: true,
        description: 'API key for authentication',
      },
      input_file: {
        name: 'input_file',
        type: 'string',
        required: true,
        description: 'Path to input file',
      },
    },
  },
};

export const ParametersEmpty: ParametersStory = {
  args: {
    parameters: {},
  },
};

// ============================================================================
// Outputs Section
// ============================================================================

const outputsMeta: Meta<typeof OutputsSection> = {
  title: 'Sidebar/Metadata/OutputsSection',
  component: OutputsSection,
  parameters: {
    layout: 'padded',
  },
};

type OutputsStory = StoryObj<typeof OutputsSection>;

export const OutputsWithMixedRequirements: OutputsStory = {
  args: {
    outputs: {
      result: {
        name: 'result',
        type: 'string',
        required: true,
        description: 'The main result of the procedure',
      },
      confidence: {
        name: 'confidence',
        type: 'number',
        required: false,
        description: 'Confidence score (0-1)',
      },
      metadata: {
        name: 'metadata',
        type: 'object',
        required: false,
        description: 'Additional metadata',
      },
    },
  },
};

export const OutputsRequired: OutputsStory = {
  args: {
    outputs: {
      status: {
        name: 'status',
        type: 'string',
        required: true,
        description: 'Execution status',
      },
      error_message: {
        name: 'error_message',
        type: 'string',
        required: true,
        description: 'Error message if failed',
      },
    },
  },
};

export const OutputsEmpty: OutputsStory = {
  args: {
    outputs: {},
  },
};

// ============================================================================
// Stages Section
// ============================================================================

const stagesMeta: Meta<typeof StagesSection> = {
  title: 'Sidebar/Metadata/StagesSection',
  component: StagesSection,
  parameters: {
    layout: 'padded',
  },
};

type StagesStory = StoryObj<typeof StagesSection>;

export const StagesMultiple: StagesStory = {
  args: {
    stages: ['initialization', 'data_loading', 'processing', 'validation', 'output_generation', 'cleanup'],
  },
};

export const StagesSimple: StagesStory = {
  args: {
    stages: ['start', 'middle', 'end'],
  },
};

export const StagesEmpty: StagesStory = {
  args: {
    stages: [],
  },
};

// ============================================================================
// Agents Section
// ============================================================================

const agentsMeta: Meta<typeof AgentsSection> = {
  title: 'Sidebar/Metadata/AgentsSection',
  component: AgentsSection,
  parameters: {
    layout: 'padded',
  },
};

type AgentsStory = StoryObj<typeof AgentsSection>;

export const AgentsSingle: AgentsStory = {
  args: {
    agents: {
      main: {
        name: 'main',
        model: 'gpt-4o',
        provider: 'openai',
        system_prompt: 'You are a helpful assistant that processes user requests and provides detailed responses.',
        tools: ['search', 'calculator', 'weather', 'done'],
      },
    },
  },
};

export const AgentsMultiple: AgentsStory = {
  args: {
    agents: {
      researcher: {
        name: 'researcher',
        model: 'gpt-4o',
        provider: 'openai',
        system_prompt: 'You are a researcher that gathers and analyzes information from various sources.',
        tools: ['web_search', 'read_file', 'done'],
      },
      writer: {
        name: 'writer',
        model: 'claude-3-5-sonnet-20241022',
        provider: 'bedrock',
        system_prompt: 'You are a professional writer that creates clear, engaging content based on research.',
        tools: ['write_file', 'done'],
      },
      editor: {
        name: 'editor',
        model: 'gpt-4o-mini',
        provider: 'openai',
        system_prompt: 'You are an editor that reviews content for clarity, grammar, and style.',
        tools: ['edit_file', 'done'],
      },
    },
  },
};

export const AgentWithDynamicPrompt: AgentsStory = {
  args: {
    agents: {
      dynamic: {
        name: 'dynamic',
        model: 'gpt-4o',
        provider: 'openai',
        system_prompt: '[Dynamic Prompt]',
        tools: ['done'],
      },
    },
  },
};

export const AgentsEmpty: AgentsStory = {
  args: {
    agents: {},
  },
};

// ============================================================================
// Tools Section
// ============================================================================

const toolsMeta: Meta<typeof ToolsSection> = {
  title: 'Sidebar/Metadata/ToolsSection',
  component: ToolsSection,
  parameters: {
    layout: 'padded',
  },
};

type ToolsStory = StoryObj<typeof ToolsSection>;

export const ToolsMany: ToolsStory = {
  args: {
    tools: ['web_search', 'read_file', 'write_file', 'edit_file', 'calculator', 'weather', 'database_query', 'send_email', 'done'],
  },
};

export const ToolsFew: ToolsStory = {
  args: {
    tools: ['search', 'done'],
  },
};

export const ToolsEmpty: ToolsStory = {
  args: {
    tools: [],
  },
};

// ============================================================================
// Specifications Section
// ============================================================================

const specificationsMeta: Meta<typeof SpecificationsSection> = {
  title: 'Sidebar/Metadata/SpecificationsSection',
  component: SpecificationsSection,
  parameters: {
    layout: 'padded',
  },
};

type SpecificationsStory = StoryObj<typeof SpecificationsSection>;

export const SpecificationsWithMultipleScenarios: SpecificationsStory = {
  args: {
    specifications: {
      text: `Feature: User Authentication
  Test user login and authentication flow

  Scenario: Successful login
    Given the user is on the login page
    When the user enters valid credentials
    Then the user should be redirected to dashboard
    And the session should be created

  Scenario: Failed login attempt
    Given the user is on the login page
    When the user enters invalid credentials
    Then an error message should be displayed
    And the user should remain on login page

  Scenario: Account lockout
    Given the user has failed login 3 times
    When the user attempts to login again
    Then the account should be locked
    And the user should see a lockout message`,
      feature_name: 'User Authentication',
      scenario_count: 3,
    },
  },
};

export const SpecificationsSingleScenario: SpecificationsStory = {
  args: {
    specifications: {
      text: `Feature: Hello World
  Basic hello world test

  Scenario: Say hello
    Given the procedure has started
    When the procedure runs
    Then it should complete successfully`,
      feature_name: 'Hello World',
      scenario_count: 1,
    },
  },
};

export const SpecificationsMissing: SpecificationsStory = {
  args: {
    specifications: null,
  },
};

// ============================================================================
// Evaluations Section
// ============================================================================

const evaluationsMeta: Meta<typeof EvaluationsSection> = {
  title: 'Sidebar/Metadata/EvaluationsSection',
  component: EvaluationsSection,
  parameters: {
    layout: 'padded',
  },
};

type EvaluationsStory = StoryObj<typeof EvaluationsSection>;

export const EvaluationsLargeDataset: EvaluationsStory = {
  args: {
    evaluations: {
      dataset_count: 100,
      evaluator_count: 7,
      runs: 10,
      parallel: true,
    },
  },
};

export const EvaluationsSmallDataset: EvaluationsStory = {
  args: {
    evaluations: {
      dataset_count: 5,
      evaluator_count: 2,
      runs: 1,
      parallel: false,
    },
  },
};

export const EvaluationsSingleCase: EvaluationsStory = {
  args: {
    evaluations: {
      dataset_count: 1,
      evaluator_count: 3,
      runs: 5,
      parallel: true,
    },
  },
};

export const EvaluationsMissing: EvaluationsStory = {
  args: {
    evaluations: null,
  },
};
