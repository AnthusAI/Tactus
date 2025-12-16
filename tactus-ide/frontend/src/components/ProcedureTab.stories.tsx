import type { Meta, StoryObj } from '@storybook/react';
import { ProcedureTab } from './ProcedureTab';

const meta: Meta<typeof ProcedureTab> = {
  title: 'Sidebar/ProcedureTab',
  component: ProcedureTab,
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof ProcedureTab>;

export const WithFullMetadata: Story = {
  args: {
    metadata: {
      description: 'A comprehensive procedure that demonstrates all available features including parameters, outputs, agents, and tools.',
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
          description: 'Maximum number of iterations to perform',
        },
        temperature: {
          name: 'temperature',
          type: 'number',
          required: false,
          default: 0.7,
          description: 'Temperature for LLM responses',
        },
      },
      outputs: {
        result: {
          name: 'result',
          type: 'string',
          required: true,
          description: 'The final processed result',
        },
        confidence: {
          name: 'confidence',
          type: 'number',
          required: false,
          description: 'Confidence score of the result',
        },
      },
      stages: ['initialization', 'processing', 'validation', 'completion'],
      agents: {
        analyzer: {
          name: 'analyzer',
          model: 'gpt-4o',
          provider: 'openai',
          system_prompt: 'You are a helpful analyzer that processes user input and provides detailed analysis.',
          tools: ['search', 'calculate', 'done'],
        },
        reviewer: {
          name: 'reviewer',
          model: 'claude-3-5-sonnet-20241022',
          provider: 'bedrock',
          system_prompt: 'You are a reviewer that validates the analysis and provides feedback.',
          tools: ['validate', 'done'],
        },
      },
      toolsets: {},
      tools: ['search', 'calculate', 'validate', 'done'],
      specifications: {
        text: `Feature: Data Processing
  Test data processing workflow

  Scenario: Process valid input
    Given the procedure has started
    When the user provides valid input
    Then the result should be generated
    And the confidence score should be above 0.8

  Scenario: Handle invalid input
    Given the procedure has started
    When the user provides invalid input
    Then an error should be raised
    And the user should be notified`,
        feature_name: 'Data Processing',
        scenario_count: 2,
      },
      evaluations: {
        dataset_count: 10,
        evaluator_count: 3,
        runs: 5,
        parallel: true,
      },
    },
    loading: false,
  },
};

export const MinimalMetadata: Story = {
  args: {
    metadata: {
      description: 'A minimal procedure with no parameters or outputs',
      parameters: {},
      outputs: {},
      stages: [],
      agents: {},
      toolsets: {},
      tools: [],
      specifications: null,
      evaluations: null,
    },
    loading: false,
  },
};

export const OnlyParameters: Story = {
  args: {
    metadata: {
      description: null,
      parameters: {
        input: {
          name: 'input',
          type: 'string',
          required: true,
        },
        debug: {
          name: 'debug',
          type: 'boolean',
          required: false,
          default: false,
        },
      },
      outputs: {},
      stages: [],
      agents: {},
      toolsets: {},
      tools: [],
      specifications: null,
      evaluations: null,
    },
    loading: false,
  },
};

export const OnlyAgents: Story = {
  args: {
    metadata: {
      description: null,
      parameters: {},
      outputs: {},
      stages: [],
      agents: {
        main: {
          name: 'main',
          model: 'gpt-4o',
          provider: 'openai',
          system_prompt: 'You are a helpful assistant.',
          tools: ['search', 'calculator', 'weather', 'done'],
        },
      },
      toolsets: {},
      tools: ['search', 'calculator', 'weather', 'done'],
      specifications: null,
      evaluations: null,
    },
    loading: false,
  },
};

export const MultipleAgents: Story = {
  args: {
    metadata: {
      description: 'A multi-agent procedure with specialized agents',
      parameters: {},
      outputs: {},
      stages: [],
      agents: {
        researcher: {
          name: 'researcher',
          model: 'gpt-4o',
          provider: 'openai',
          system_prompt: 'You are a researcher that gathers information.',
          tools: ['web_search', 'read_file', 'done'],
        },
        writer: {
          name: 'writer',
          model: 'claude-3-5-sonnet-20241022',
          provider: 'bedrock',
          system_prompt: 'You are a writer that creates content based on research.',
          tools: ['write_file', 'done'],
        },
        editor: {
          name: 'editor',
          model: 'gpt-4o-mini',
          provider: 'openai',
          system_prompt: 'You are an editor that reviews and improves content.',
          tools: ['edit_file', 'done'],
        },
      },
      toolsets: {},
      tools: ['web_search', 'read_file', 'write_file', 'edit_file', 'done'],
      specifications: null,
      evaluations: null,
    },
    loading: false,
  },
};

export const WithSpecificationsOnly: Story = {
  args: {
    metadata: {
      description: 'Procedure with BDD specifications',
      parameters: {},
      outputs: {},
      stages: [],
      agents: {},
      toolsets: {},
      tools: [],
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
      evaluations: null,
    },
    loading: false,
  },
};

export const WithEvaluationsOnly: Story = {
  args: {
    metadata: {
      description: 'Procedure with Pydantic evaluations',
      parameters: {},
      outputs: {},
      stages: [],
      agents: {},
      toolsets: {},
      tools: [],
      specifications: null,
      evaluations: {
        dataset_count: 25,
        evaluator_count: 5,
        runs: 3,
        parallel: true,
      },
    },
    loading: false,
  },
};

export const MissingSpecificationsAndEvaluations: Story = {
  args: {
    metadata: {
      description: 'Procedure without specifications or evaluations - shows warnings',
      parameters: {
        input: {
          name: 'input',
          type: 'string',
          required: true,
        },
      },
      outputs: {
        result: {
          name: 'result',
          type: 'string',
          required: true,
        },
      },
      stages: ['start', 'process', 'end'],
      agents: {
        worker: {
          name: 'worker',
          model: 'gpt-4o',
          provider: 'openai',
          system_prompt: 'You are a worker agent.',
          tools: ['done'],
        },
      },
      toolsets: {},
      tools: ['done'],
      specifications: null,
      evaluations: null,
    },
    loading: false,
  },
};

export const DynamicPrompt: Story = {
  args: {
    metadata: {
      description: 'Procedure with dynamic system prompt',
      parameters: {},
      outputs: {},
      stages: [],
      agents: {
        dynamic: {
          name: 'dynamic',
          model: 'gpt-4o',
          provider: 'openai',
          system_prompt: '[Dynamic Prompt]',
          tools: ['done'],
        },
      },
      toolsets: {},
      tools: ['done'],
      specifications: null,
      evaluations: null,
    },
    loading: false,
  },
};

export const Loading: Story = {
  args: {
    metadata: null,
    loading: true,
  },
};

export const NoMetadata: Story = {
  args: {
    metadata: null,
    loading: false,
  },
};

export const LongDescription: Story = {
  args: {
    metadata: {
      description: 'This is a very long description that explains in great detail what this procedure does. It spans multiple sentences and provides comprehensive information about the purpose, functionality, and expected behavior of the procedure. This helps users understand exactly what will happen when they execute this procedure and what they should expect as outputs.',
      parameters: {
        input: {
          name: 'input',
          type: 'string',
          required: true,
        },
      },
      outputs: {
        result: {
          name: 'result',
          type: 'string',
          required: true,
        },
      },
      stages: [],
      agents: {},
      toolsets: {},
      tools: [],
      specifications: null,
      evaluations: null,
    },
    loading: false,
  },
};
