Feature: DSPy Language Model Configuration
  As a Tactus developer
  I want to configure and use language models through DSPy
  So that I can leverage different LLM providers and configurations

  Background:
    Given dspy is installed as a dependency

  # Basic Configuration Tests

  Scenario: Configure OpenAI model
    When I configure an LM with "openai/gpt-4o-mini"
    Then the LM should be available for use
    And the current LM should be set

  Scenario: Configure Anthropic model
    When I configure an LM with "anthropic/claude-3-5-sonnet-20241022"
    Then the LM should be available for use
    And the current LM should be set

  Scenario: Configure with custom parameters
    When I configure an LM with model "openai/gpt-4o-mini" and temperature 0.3
    Then the LM should be available for use
    And the LM temperature should be 0.3

  Scenario: Configure with max_tokens parameter
    When I configure an LM with model "openai/gpt-4o-mini" and max_tokens 500
    Then the LM should be available for use
    And the LM max_tokens should be 500

  # Global State Management

  Scenario: Get current LM after configuration
    When I configure an LM with "openai/gpt-4o-mini"
    Then I can retrieve the current LM
    And the current LM model should be "openai/gpt-4o-mini"

  Scenario: Switch between multiple LMs
    When I configure an LM with "openai/gpt-4o-mini"
    And I configure another LM with "anthropic/claude-3-5-sonnet-20241022"
    Then the current LM model should be "anthropic/claude-3-5-sonnet-20241022"

  # Tactus DSL Integration

  Scenario: LM configuration in Tactus procedure
    Given a Tactus procedure with LM configuration:
      """
      Procedure "test_lm" {
        output = {
          lm_configured = field.boolean{required = true}
        },
        function(input)
          LM("openai/gpt-4o-mini")
          return {lm_configured = true}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output lm_configured should be true

  Scenario: LM with curried syntax in Tactus
    Given a Tactus procedure with curried LM configuration:
      """
      Procedure "test_curried_lm" {
        output = {
          lm_configured = field.boolean{required = true}
        },
        function(input)
          LM "openai/gpt-4o-mini" {
            temperature = 0.5,
            max_tokens = 1000
          }
          return {lm_configured = true}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output lm_configured should be true

  Scenario: Multiple LM configurations in same procedure
    Given a Tactus procedure with multiple LM configurations:
      """
      Procedure "test_multiple_lms" {
        output = {
          first_model = field.string{required = true},
          second_model = field.string{required = true}
        },
        function(input)
          -- Configure first LM
          local lm1 = LM("openai/gpt-4o-mini")
          local first = "gpt-4o-mini"

          -- Configure second LM
          local lm2 = LM("anthropic/claude-3-5-sonnet-20241022")
          local second = "claude-3-5-sonnet"

          return {
            first_model = first,
            second_model = second
          }
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output first_model should be "gpt-4o-mini"
    And the output second_model should be "claude-3-5-sonnet"

  # Environment Variable Integration

  Scenario: LM uses environment variable for API key
    Given environment variable "OPENAI_API_KEY" is set to "test-key"
    When I configure an LM with "openai/gpt-4o-mini" without explicit api_key
    Then the LM should use the environment API key

  Scenario: Override environment variable with explicit API key
    Given environment variable "OPENAI_API_KEY" is set to "env-key"
    When I configure an LM with model "openai/gpt-4o-mini" and api_key "explicit-key"
    Then the LM should use "explicit-key" instead of environment key

  # Error Handling

  Scenario: Error on invalid model name
    When I try to configure an LM with invalid model "invalid/model-name"
    Then an error should be raised
    And the error should mention "invalid model"

  Scenario: Error on missing required configuration
    When I try to configure an LM without a model parameter
    Then an error should be raised
    And the error should mention "model is required"

  # Advanced Configuration

  Scenario: Configure LM with custom API base URL
    When I configure an LM with model "openai/gpt-4o-mini" and api_base "https://custom.api.com"
    Then the LM should be available for use
    And the LM should use the custom API base

  Scenario: Configure LM with all parameters
    When I configure an LM with full configuration:
      | parameter    | value                    |
      | model        | openai/gpt-4o-mini       |
      | temperature  | 0.7                      |
      | max_tokens   | 2000                     |
      | api_key      | test-key                 |
      | api_base     | https://api.openai.com   |
      | top_p        | 0.9                      |
    Then the LM should be available for use
    And all parameters should be properly set

  # Model-specific Configurations

  Scenario: Configure Bedrock model with region
    When I configure an LM with "bedrock/anthropic.claude-3-5-sonnet" and region "us-west-2"
    Then the LM should be available for use
    And the LM should use AWS region "us-west-2"

  Scenario: Configure local model
    When I configure an LM with "ollama/llama3.2"
    Then the LM should be available for use
    And the LM should connect to local Ollama instance

  # State Persistence

  Scenario: LM configuration persists across function calls
    Given a Tactus procedure that configures LM once:
      """
      Procedure "test_persistence" {
        output = {
          model_in_func1 = field.string{required = true},
          model_in_func2 = field.string{required = true}
        },
        function(input)
          LM("openai/gpt-4o-mini")

          local function get_model_1()
            local lm = get_current_lm()
            return "gpt-4o-mini"
          end

          local function get_model_2()
            local lm = get_current_lm()
            return "gpt-4o-mini"
          end

          return {
            model_in_func1 = get_model_1(),
            model_in_func2 = get_model_2()
          }
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output model_in_func1 should be "gpt-4o-mini"
    And the output model_in_func2 should be "gpt-4o-mini"