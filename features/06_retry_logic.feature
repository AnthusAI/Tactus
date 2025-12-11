Feature: Retry Logic
  As a workflow developer
  I want to automatically retry failed operations
  So that transient failures don't break workflows

  Background:
    Given a Tactus workflow environment
    And the retry primitive is initialized

  Scenario: Successful operation on first try
    When I execute an operation that succeeds
    Then it should succeed immediately
    And no retries should be attempted

  Scenario: Success after retries
    Given an operation that fails 2 times then succeeds
    When I execute with max_retries 3
    Then the operation should eventually succeed
    And it should be attempted 3 times total

  Scenario: All retries exhausted
    Given an operation that always fails
    When I execute with max_retries 3
    Then all retries should be exhausted
    And a final error should be raised

  Scenario: Exponential backoff
    Given an operation that fails twice
    When I execute with exponential backoff strategy
    Then retry delays should increase: 1s, 2s, 4s
    And the operation should eventually succeed

  Scenario: Conditional retry based on error type
    Given operations that fail with different errors
    When I retry only on "NetworkError"
    Then "NetworkError" should trigger retries
    And "ValidationError" should fail immediately

  Scenario: Circuit breaker pattern
    Given an operation that fails consistently
    When I execute with circuit breaker enabled
    And failure threshold is 5
    Then after 5 failures, the circuit should open
    And subsequent calls should fail fast without attempting
