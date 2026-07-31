Feature: Durable external-child wait
  As a workflow author
  I want a procedure to checkpoint while durable external children run
  So that it can resume without holding compute or losing child identity

  Scenario: Suspend on nonterminal children
    Given a procedure has stable external child references
    When it waits for all children and at least one remains nonterminal
    Then Tactus checkpoints the wait request
    And exposes a distinct waiting-for-children outcome
    And does not use an in-memory thread or fixed completion timeout

  Scenario: Replay after external progress
    Given a waiting procedure is resumed
    When the host reports terminal states for every requested child
    Then the wait checkpoint returns the terminal child results
    And execution continues exactly once after the wait

  Scenario: Preserve partial failures
    Given several external children complete with mixed terminal states
    When the wait resolves
    Then each child result remains independently visible
    And successful siblings are not discarded or cancelled
