Feature: Classify Primitive
  As a workflow developer
  I want to use smart classification with built-in retry
  So that I can reliably classify text without manual retry logic

  Background:
    Given a Tactus workflow environment
    And the Classify primitive is available

  # Binary Classification
  Scenario: Binary classification returns valid response
    Given a Classify call with classes ["Yes", "No"]
    And the prompt is "Did the agent greet the customer?"
    When Classify is invoked with input "Hello! How can I help you today?"
    Then the result value should be one of ["Yes", "No"]
    And the result should include confidence
    And the result should include explanation

  Scenario: Binary classification with Yes answer
    Given a Classify call with classes ["Yes", "No"]
    And the prompt is "Is this text positive?"
    And the LLM will respond with "Yes"
    When Classify is invoked with input "I love this product!"
    Then the result value should be "Yes"

  Scenario: Binary classification with No answer
    Given a Classify call with classes ["Yes", "No"]
    And the prompt is "Does the text mention an error?"
    And the LLM will respond with "No"
    When Classify is invoked with input "Everything is working great"
    Then the result value should be "No"

  # Multi-class Classification
  Scenario: Multi-class classification
    Given a Classify call with classes ["positive", "negative", "neutral"]
    And the prompt is "What is the sentiment?"
    When Classify is invoked with input "The service was okay"
    Then the result value should be one of ["positive", "negative", "neutral"]

  Scenario: Multi-class with specific result
    Given a Classify call with classes ["high", "medium", "low"]
    And the prompt is "What is the urgency level?"
    And the LLM will respond with "high"
    When Classify is invoked with input "System is down! Need help immediately!"
    Then the result value should be "high"

  # Retry Logic
  Scenario: Invalid response triggers retry
    Given a Classify call with classes ["Yes", "No"]
    And the LLM will respond with "Maybe" then "Yes"
    When Classify is invoked
    Then the result value should be "Yes"
    And the retry_count should be 1

  Scenario: Multiple retries before success
    Given a Classify call with classes ["Yes", "No"]
    And max_retries is 3
    And the LLM will respond with "Invalid" then "Unknown" then "Yes"
    When Classify is invoked
    Then the result value should be "Yes"
    And the retry_count should be 2

  Scenario: Max retries exceeded returns error
    Given a Classify call with classes ["Yes", "No"]
    And max_retries is 2
    And the LLM will always respond with "Invalid"
    When Classify is invoked
    Then the result should contain an error
    And the retry_count should be 2

  Scenario: Retry with conversational feedback
    Given a Classify call with classes ["Yes", "No"]
    And the LLM will respond with "Maybe" then "Yes"
    When Classify is invoked
    Then the second LLM call should include:
      | content                    |
      | valid classifications      |
      | "Yes", "No"               |

  # Confidence Extraction
  Scenario: High confidence from definite language
    Given a Classify call with classes ["Yes", "No"]
    And the LLM will respond with "Yes. The text definitely indicates agreement."
    When Classify is invoked
    Then the result confidence should be greater than 0.9

  Scenario: Medium confidence from likely language
    Given a Classify call with classes ["Yes", "No"]
    And the LLM will respond with "Yes. The text probably indicates agreement."
    When Classify is invoked
    Then the result confidence should be between 0.7 and 0.9

  Scenario: Low confidence from uncertain language
    Given a Classify call with classes ["Yes", "No"]
    And the LLM will respond with "Yes. It's possible this indicates agreement, though uncertain."
    When Classify is invoked
    Then the result confidence should be less than 0.7

  Scenario: Confidence mode can be disabled
    Given a Classify call with classes ["Yes", "No"]
    And confidence_mode is "none"
    When Classify is invoked
    Then the result confidence should be null

  # Response Parsing
  Scenario: Parse classification from first line
    Given a Classify call with classes ["Yes", "No"]
    And the LLM will respond with:
      """
      Yes
      The agent clearly greeted the customer by saying "Hello"
      """
    When Classify is invoked
    Then the result value should be "Yes"
    And the explanation should contain "greeted"

  Scenario: Parse classification with formatting
    Given a Classify call with classes ["Yes", "No"]
    And the LLM will respond with "**Yes** - because of the greeting"
    When Classify is invoked
    Then the result value should be "Yes"

  Scenario: Parse classification with prefix match
    Given a Classify call with classes ["Yes", "No"]
    And the LLM will respond with "Yes, the agent greeted them"
    When Classify is invoked
    Then the result value should be "Yes"

  # Reusable Classifier
  Scenario: Create reusable classifier without input
    Given a Classify call with classes ["positive", "negative", "neutral"]
    And no input is provided
    When Classify is invoked
    Then the result should be a ClassifyHandle
    And the handle can be called multiple times

  Scenario: One-shot classification with input
    Given a Classify call with classes ["Yes", "No"]
    And input is "Hello there!"
    When Classify is invoked
    Then the result should be a classification result
    And not a ClassifyHandle

  # Configuration Options
  Scenario: Custom temperature setting
    Given a Classify call with classes ["Yes", "No"]
    And temperature is 0.1
    When Classify is invoked
    Then the internal agent should use temperature 0.1

  Scenario: Custom model setting
    Given a Classify call with classes ["Yes", "No"]
    And model is "gpt-4"
    When Classify is invoked
    Then the internal agent should use model "gpt-4"

  Scenario: Default max_retries is 3
    Given a Classify call with classes ["Yes", "No"]
    And the LLM will always respond with "Invalid"
    When Classify is invoked
    Then the retry_count should be 3

  # Edge Cases
  Scenario: Empty input handling
    Given a Classify call with classes ["Yes", "No"]
    When Classify is invoked with empty input
    Then the classification should still attempt

  Scenario: Classification with NA option
    Given a Classify call with classes ["Yes", "No", "NA"]
    And the prompt is "Does this apply?"
    And the LLM will respond with "NA"
    When Classify is invoked with input "Not enough information"
    Then the result value should be "NA"

  Scenario: Case insensitive matching
    Given a Classify call with classes ["Yes", "No"]
    And the LLM will respond with "YES"
    When Classify is invoked
    Then the result value should be "Yes"

  Scenario: Missing required classes raises error
    Given a Classify call without classes
    When Classify is invoked
    Then an error should be raised
    And the error message should mention "classes"

  Scenario: Missing required prompt raises error
    Given a Classify call with classes ["Yes", "No"]
    And no prompt is provided
    When Classify is invoked
    Then an error should be raised
    And the error message should mention "prompt"
