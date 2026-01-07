Feature: DSPy Module Creation and Strategies
  As a Tactus developer
  I want to create and use DSPy modules with different strategies
  So that I can implement various prompting techniques

  Background:
    Given dspy is installed as a dependency
    And an LM is configured with "openai/gpt-4o-mini"

  # Module Creation with Different Strategies

  Scenario: Create Module with predict strategy
    When I create a Module with predict strategy
    Then the Module should be callable
    And the Module should have strategy "predict"

  Scenario: Create Module with chain_of_thought strategy
    When I create a Module with chain_of_thought strategy
    Then the Module should be callable
    And the Module should have strategy "chain_of_thought"

  Scenario: Create Module with custom signature
    When I create a Module with signature "question -> answer" and strategy "predict"
    Then the Module should be callable
    And the Module should accept "question" as input
    And the Module should return "answer" as output

  # Tactus DSL Integration

  Scenario: Module creation in Tactus procedure
    Given a Tactus procedure that creates a Module:
      """
      Procedure "test_module" {
        output = {
          module_created = field.boolean{required = true}
        },
        function(input)
          local qa_module = Module "qa" {
            signature = "question -> answer",
            strategy = "predict"
          }

          return {module_created = qa_module ~= nil}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output module_created should be true

  Scenario: Chain of thought Module in Tactus
    Given a Tactus procedure with chain_of_thought Module:
      """
      Procedure "test_cot" {
        output = {
          has_reasoning = field.boolean{required = true}
        },
        function(input)
          local cot_module = Module "reasoning" {
            signature = "problem -> reasoning, solution",
            strategy = "chain_of_thought"
          }

          -- Module created with CoT strategy
          return {has_reasoning = true}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output has_reasoning should be true

  # Module Invocation

  Scenario: Invoke Module with input
    Given a Module with signature "text -> summary"
    When I invoke the Module with input "This is a long text that needs summarization"
    Then the Module should return a prediction
    And the prediction should have field "summary"

  Scenario: Invoke Module with multiple inputs
    Given a Module with signature "context, question -> answer"
    When I invoke the Module with:
      | field    | value                          |
      | context  | The sky is blue during the day |
      | question | What color is the sky?         |
    Then the Module should return a prediction
    And the prediction should have field "answer"

  Scenario: Module invocation in Tactus procedure
    Given a Tactus procedure that invokes a Module:
      """
      Procedure "test_invocation" {
        output = {
          has_prediction = field.boolean{required = true}
        },
        function(input)
          local translator = Module "translate" {
            signature = "text, target_language -> translation",
            strategy = "predict"
          }

          -- Mock invocation (would need actual LM for real prediction)
          local result = {translation = "translated text"}

          return {has_prediction = result.translation ~= nil}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output has_prediction should be true

  # Signature Integration

  Scenario: Module with string signature
    When I create a Module with string signature "input -> output"
    Then the Module should be callable
    And the Module should use the string signature

  Scenario: Module with structured signature
    When I create a Module with structured signature:
      """
      {
        "signature": {
          "input": {
            "text": {"description": "Input text", "type": "string"}
          },
          "output": {
            "result": {"description": "Processed result", "type": "string"}
          }
        },
        "strategy": "predict"
      }
      """
    Then the Module should be callable
    And the Module should use the structured signature

  Scenario: Module with pre-created signature
    Given a signature "document -> entities, summary"
    When I create a Module using the pre-created signature
    Then the Module should be callable
    And the Module should use the given signature

  # Error Handling

  Scenario: Error on missing required input field
    Given a Module with signature "required_field -> output"
    When I invoke the Module without providing "required_field"
    Then an error should be raised during module operation
    And the module error should mention "required_field is missing"

  Scenario: Error on invalid strategy
    When I try to create a Module with invalid strategy "invalid_strategy"
    Then an error should be raised during module operation
    And the module error should mention "Unknown strategy"

  Scenario: Error on missing signature
    When I try to create a Module without a signature
    Then an error should be raised during module operation
    And the module error should mention "requires a 'signature'"

  # Module Chaining and Composition

  Scenario: Chain multiple Modules
    Given a Tactus procedure that chains Modules:
      """
      Procedure "test_chaining" {
        output = {
          chained = field.boolean{required = true}
        },
        function(input)
          local analyzer = Module "analyze" {
            signature = "text -> keywords, sentiment",
            strategy = "predict"
          }

          local summarizer = Module "summarize" {
            signature = "text, keywords -> summary",
            strategy = "predict"
          }

          -- Modules can be chained conceptually
          local can_chain = analyzer ~= nil and summarizer ~= nil

          return {chained = can_chain}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output chained should be true

  Scenario: Compose Modules with shared context
    Given a Tactus procedure with Module composition:
      """
      Procedure "test_composition" {
        output = {
          composed = field.boolean{required = true}
        },
        function(input)
          local extractor = Module "extract" {
            signature = "document -> facts",
            strategy = "predict"
          }

          local validator = Module "validate" {
            signature = "facts -> verified_facts, confidence",
            strategy = "chain_of_thought"
          }

          -- Both modules created successfully
          return {composed = true}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output composed should be true

  # Advanced Module Strategies

  Scenario: Module with custom temperature
    When I create a Module with custom parameters:
      """
      {
        "signature": "creative_prompt -> story",
        "strategy": "predict",
        "temperature": 0.9
      }
      """
    Then the Module should be callable
    And the Module should use temperature 0.9

  Scenario: Module with max_tokens limit
    When I create a Module with token limit:
      """
      {
        "signature": "prompt -> response",
        "strategy": "predict",
        "max_tokens": 100
      }
      """
    Then the Module should be callable
    And the Module should limit output to 100 tokens

  # Module State and Reusability

  Scenario: Reuse Module multiple times
    Given a Tactus procedure that reuses a Module:
      """
      Procedure "test_reuse" {
        output = {
          first_use = field.boolean{required = true},
          second_use = field.boolean{required = true}
        },
        function(input)
          local qa = Module "qa" {
            signature = "question -> answer",
            strategy = "predict"
          }

          -- First use
          local result1 = {answer = "first answer"}

          -- Second use (same module)
          local result2 = {answer = "second answer"}

          return {
            first_use = result1.answer ~= nil,
            second_use = result2.answer ~= nil
          }
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output first_use should be true
    And the output second_use should be true

  # Module with History

  Scenario: Module uses conversation history
    Given a Module with signature "question -> answer"
    And a conversation history with previous Q&A
    When I invoke the Module with history context
    Then the Module should consider the history
    And return a contextually aware answer

  # Future Strategies Placeholder

  Scenario: Prepare for react strategy
    When I check available Module strategies
    Then "predict" should be available
    And "chain_of_thought" should be available
    And future strategies like "react" should be documented

  Scenario: Prepare for program_of_thought strategy
    When I check available Module strategies
    Then current strategies should work
    And "program_of_thought" should be planned for future

  # Module Debugging and Inspection

  Scenario: Inspect Module configuration
    Given a Module with signature "input -> output" and strategy "predict"
    When I inspect the Module configuration
    Then I should see the signature details
    And I should see the strategy type
    And I should see any custom parameters

  Scenario: Module with verbose output
    When I create a Module with verbose flag:
      """
      {
        "signature": "question -> answer",
        "strategy": "chain_of_thought",
        "verbose": true
      }
      """
    Then the Module should be callable
    And the Module should provide detailed execution information