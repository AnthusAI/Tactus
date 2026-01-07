Feature: Agent Primitives
  As a workflow developer
  I want to invoke AI agents with prompts
  So that workflows can leverage language models

  Background:
  Given a Tactus workflow environment
  And the agent primitive is initialized
  And an LLM backend is configured

  Scenario: Simple agent call
  When I call agent with Prompt "Summarize: Tactus is a workflow DSL"
  Then the agent should respond
  And the response should contain a summary

  Scenario: Agent call with system message
  Given a system message "You are a helpful research assistant"
  When I call agent with Prompt "What is machine learning?"
  Then the response should be in assistant character
  And the tone should be helpful and informative

  Scenario: Structured output from agent
  When I request json format
  And I call agent with Prompt "List 3 programming languages"
  Then the response should be valid JSON
  And it should contain an array of 3 languages

  Scenario: Multi-turn conversation
  Given a conversation context
  When I send message "What is Python?"
  And the agent responds with Python explanation
  And I send follow-up "What about type hints?"
  Then the agent should respond in context
  And reference the previous Python discussion

  Scenario: Agent with tools
  Given agent has access to tools:
  | tool  | description  |
  | search_web  | Search the internet  |
  | calculate  | Perform calculations  |
  When I ask "What is 15% of 2500?"
  Then the agent should use the calculate tool
  And return the correct answer: 375

  Scenario: Agent response validation
  When I call agent with Prompt "Generate a valid email address"
  And I validate the response with pattern "[a-z]+@[a-z]+\.[a-z]+"
  Then the validation should pass
  And the response should be a valid email format

  Scenario: Temperature control for creativity
  When I call agent with temperature 0.0 and Prompt "Pick a number"
  Then responses should be deterministic
  When I call agent with temperature 1.5 and Prompt "Write a creative story"
  Then responses should be diverse and creative

  Scenario: Token limit handling
  When I call agent with max_tokens 50
  And the prompt is "Write a detailed essay on climate change"
  Then the response should be truncated at approximately 50 tokens
  And it should end gracefully

  Scenario: Error handling for invalid prompts
  When I call agent with an empty prompt
  Then an error should be raised
  And the workflow can handle the validation error
