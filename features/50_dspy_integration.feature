Feature: DSPy Integration
  As a Tactus developer
  I want DSPy to be available as the LLM backend
  So that I can use DSPy's prompt optimization and module system

  Scenario: DSPy is importable
    Given dspy is installed as a dependency
    Then dspy should be importable from Python
    And tactus.dspy module should be importable

  Scenario: Configure LM from Python
    Given dspy is installed as a dependency
    When I configure an LM with "openai/gpt-4o-mini"
    Then the LM should be available for use
    And the current LM should be set

  Scenario: LM primitive in Tactus code
    Given a Tactus procedure that uses the LM primitive
    When the procedure is parsed
    Then the LM should be configured

  Scenario: Parse simple signature
    Given dspy is installed as a dependency
    When I create a signature "question -> answer"
    Then it should have input field "question"
    And it should have output field "answer"

  Scenario: Parse multi-field signature
    Given dspy is installed as a dependency
    When I create a signature "context, question -> reasoning, answer"
    Then it should have input fields "context" and "question"
    And it should have output fields "reasoning" and "answer"

  Scenario: Signature primitive in Tactus code
    Given a Tactus procedure that uses the Signature primitive
    When the procedure is parsed
    Then the signature should be created

  Scenario: Create structured signature with descriptions
    Given dspy is installed as a dependency
    When I create a structured signature with field descriptions
    Then it should have input field "question"
    And input field "question" should have description "The question to answer"
    And it should have output field "answer"
    And output field "answer" should have description "The answer"

  Scenario: Structured signature in Tactus code
    Given a Tactus procedure with a structured Signature
    When the procedure is parsed
    Then the structured signature should be created with descriptions

  Scenario: Create Module with predict strategy
    Given dspy is installed as a dependency
    When I create a Module with predict strategy
    Then the Module should be callable
    And the Module should have strategy "predict"

  Scenario: Module primitive in Tactus code
    Given a Tactus procedure that uses the Module primitive
    When the procedure is parsed
    Then the Module should be created successfully

  Scenario: Create Module with chain_of_thought strategy
    Given dspy is installed as a dependency
    When I create a Module with chain_of_thought strategy
    Then the Module should be callable
    And the Module should have strategy "chain_of_thought"

  Scenario: Chain of thought Module in Tactus code
    Given a Tactus procedure that uses the chain_of_thought Module
    When the procedure is parsed
    Then the Module should be created successfully

  Scenario: Create History and manage messages
    Given dspy is installed as a dependency
    When I create a History
    And I add a message to history
    Then the history should have 1 message
    And I can retrieve the messages

  Scenario: History primitive in Tactus code
    Given a Tactus procedure that uses the History primitive
    When the procedure is parsed
    Then the History should be usable

  Scenario: Create Prediction and access fields
    Given dspy is installed as a dependency
    When I create a Prediction with fields
    Then I can access prediction fields as attributes
    And I can get prediction data as a dictionary

  Scenario: Prediction wraps DSPy Prediction
    Given dspy is installed as a dependency
    When I wrap a DSPy Prediction
    Then the TactusPrediction should delegate to the underlying prediction

  Scenario: Create DSPy Agent stdlib
    Given dspy is installed as a dependency
    When I create a DSPy Agent with system prompt
    Then the agent should have a turn method
    And the agent should have history management

  Scenario: DSPy Agent manages conversation history
    Given dspy is installed as a dependency
    And I create a DSPy Agent with system prompt
    When I access the agent's history
    Then the history should be empty initially
    And I can add messages to the agent's history
