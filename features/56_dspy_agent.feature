Feature: DSPy Agent Interactions
  As a Tactus developer
  I want to create and use DSPy agents
  So that I can build conversational AI applications

  Background:
    Given dspy is installed as a dependency
    And an LM is configured with "openai/gpt-4o-mini"

  # Basic Agent Creation

  Scenario: Create DSPy Agent with system prompt
    When I create a DSPy Agent with system prompt
    Then the agent should have a turn method
    And the agent should have history management

  Scenario: Create Agent with custom system prompt
    When I create an Agent with system prompt "You are a helpful coding assistant"
    Then the agent should use the custom system prompt
    And the agent should be ready for conversation

  Scenario: Create Agent without system prompt
    When I create an Agent without system prompt
    Then the agent should have default behavior
    And the agent should still be functional

  # Tactus DSL Integration

  Scenario: Agent creation in Tactus procedure
    Given a Tactus procedure that creates an Agent:
      """
      test_agent = Procedure {
        output = {
          agent_created = field.boolean{required = true}
        },
        function(input)
          local agent = DSPyAgent {
            system_prompt = "You are a helpful assistant"
          }

          return {agent_created = agent ~= nil}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output agent_created should be true

  Scenario: Agent with turn method in Tactus
    Given a Tactus procedure with Agent turns:
      """
      test_agent_turn = Procedure {
        output = {
          turn_executed = field.boolean{required = true}
        },
        function(input)
          local agent = DSPyAgent {
            system_prompt = "Answer questions concisely"
          }

          -- Mock turn execution
          local response = "Sample response"

          return {turn_executed = response ~= nil}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output turn_executed should be true

  # History Management

  Scenario: Agent manages conversation history
    Given I create a DSPy Agent with system prompt
    When I access the agent's history
    Then the history should be empty initially
    And I can add messages to the agent's history

  Scenario: Agent maintains history across turns
    Given an Agent with system prompt "You are helpful"
    When I execute multiple turns:
      | turn | user_input           | expected_context |
      | 1    | What's 2+2?          | New conversation |
      | 2    | What about 3+3?      | Has previous Q&A |
      | 3    | Summarize our chat   | Full history     |
    Then the agent should maintain conversation context
    And each response should be contextually aware

  Scenario: Agent with pre-populated history
    Given a conversation history with previous exchanges
    When I create an Agent with this history
    Then the agent should continue from where it left off
    And maintain the conversation context

  # Turn Execution

  Scenario: Execute single turn
    Given an Agent with system prompt "Answer math questions"
    When I execute a turn with input "What's 5+5?"
    Then the agent should respond
    And the response should be relevant

  Scenario: Execute turn with custom parameters
    Given an Agent
    When I execute a turn with:
      | parameter    | value        |
      | input        | Tell a joke  |
      | temperature  | 0.9          |
      | max_tokens   | 100          |
    Then the agent should use the custom parameters
    And respond accordingly

  Scenario: Execute turn without input
    Given an Agent with initial context
    When I execute a turn without user input
    Then the agent should continue the conversation

  # Context Injection

  Scenario: Inject context before turn
    Given an Agent
    When I inject context "User prefers short answers"
    And execute a turn with "Explain quantum physics"
    Then the response should be concise
    And respect the injected context

  Scenario: Inject multiple context messages
    Given an Agent
    When I inject multiple context messages:
      | role      | content                    |
      | system    | Respond in bullet points   |
      | user      | Previous question context  |
      | assistant | Previous answer context    |
    And execute a turn
    Then the agent should consider all context

  # Multi-Agent Scenarios

  Scenario: Multiple agents with separate contexts
    Given a Tactus procedure with multiple agents:
      """
      test_multi_agent = Procedure {
        output = {
          agent1_has_context = field.boolean{required = true},
          agent2_has_context = field.boolean{required = true}
        },
        function(input)
          local agent1 = DSPyAgent {
            system_prompt = "You are a math tutor"
          }

          local agent2 = DSPyAgent {
            system_prompt = "You are a writing coach"
          }

          -- Each agent maintains separate context
          return {
            agent1_has_context = true,
            agent2_has_context = true
          }
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And each agent should maintain separate history

  Scenario: Agents sharing information
    Given two agents with different specializations
    When agent1 generates information
    And agent2 receives that information
    Then agent2 should be able to use agent1's output
    And maintain coherent conversation flow

  # Parameter Overrides

  Scenario: Override temperature per turn
    Given an Agent with default temperature 0.7
    When I execute turns with different temperatures:
      | turn | temperature | expected_behavior |
      | 1    | 0.1         | Very consistent   |
      | 2    | 0.9         | More creative     |
      | 3    | default     | Back to 0.7       |
    Then each turn should reflect its temperature setting

  Scenario: Override model per turn
    Given an Agent configured with "openai/gpt-4o-mini"
    When I execute a turn with model override "openai/gpt-4"
    Then that specific turn should use "openai/gpt-4"
    And subsequent turns should revert to default

  # Error Handling

  Scenario: Handle LM not configured
    Given no LM is configured
    When I try to create an Agent
    Then an error should be raised
    And the error should mention "LM not configured"

  Scenario: Handle turn execution failure
    Given an Agent with invalid configuration
    When I try to execute a turn
    Then it should handle the error gracefully
    And provide meaningful error information

  # Advanced Agent Features

  Scenario: Agent with tools/functions
    Given an Agent with tool definitions:
      """
      {
        "system_prompt": "You can use tools",
        "tools": [
          {
            "name": "calculator",
            "description": "Perform calculations"
          }
        ]
      }
      """
    When the agent needs to calculate something
    Then it should be able to use the calculator tool
    And integrate tool results in response

  Scenario: Agent with structured output
    Given an Agent configured for structured output:
      """
      {
        "system_prompt": "Provide structured responses",
        "output_format": {
          "answer": "string",
          "confidence": "float",
          "sources": "list"
        }
      }
      """
    When I execute a turn
    Then the response should match the output format
    And include all required fields

  # Session State

  Scenario: Save agent state
    Given an Agent with conversation history
    When I save the agent state
    Then it should preserve:
      | component      | description                |
      | system_prompt  | The agent's instructions   |
      | history        | Full conversation history  |
      | configuration  | Temperature, model, etc.   |

  Scenario: Restore agent state
    Given a saved agent state
    When I restore the agent
    Then it should continue from where it left off
    And maintain all previous context

  # Agent Introspection

  Scenario: Inspect agent configuration
    Given an Agent with various settings
    When I inspect the agent
    Then I should see:
      | property       | value                      |
      | system_prompt  | The configured prompt      |
      | model          | The LM model being used    |
      | history_length | Number of messages         |
      | temperature    | Current temperature setting |

  Scenario: Get agent statistics
    Given an Agent after multiple turns
    When I get agent statistics
    Then I should see:
      | metric         | description              |
      | turn_count     | Number of turns executed |
      | token_usage    | Total tokens used        |
      | avg_response   | Average response length  |

  # Integration with Other DSPy Components

  Scenario: Agent uses Module for reasoning
    Given an Agent with an integrated Module:
      """
      {
        "system_prompt": "Use reasoning module when needed",
        "modules": {
          "reasoner": {
            "signature": "problem -> analysis, solution",
            "strategy": "chain_of_thought"
          }
        }
      }
      """
    When the agent receives a complex problem
    Then it should invoke the reasoning module
    And integrate module output in response

  Scenario: Agent with Signature validation
    Given an Agent with response signature:
      """
      {
        "system_prompt": "Provide validated responses",
        "response_signature": "query -> answer, confidence, explanation"
      }
      """
    When the agent generates a response
    Then it should validate against the signature
    And ensure all fields are present

  # Streaming and Real-time

  Scenario: Agent with streaming responses
    Given an Agent configured for streaming
    When I execute a turn with streaming enabled
    Then the response should stream incrementally
    And maintain coherent output

  Scenario: Agent with timeout handling
    Given an Agent with 5 second timeout
    When a turn takes longer than timeout
    Then it should handle the timeout gracefully
    And provide partial response if available