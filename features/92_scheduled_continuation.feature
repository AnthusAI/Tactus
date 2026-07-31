Feature: Durable scheduled continuation
  As a procedure author
  I want to durably defer a procedure until a host-scheduled time
  So that transient external conditions release the worker without being mistaken for completion

  Scenario: A procedure defers without blocking a worker
    Given a procedure requests a stable continuation key and a future resume time
    When it calls Procedure.defer
    Then Tactus checkpoints the normalized scheduled continuation request
    And exposes a distinct waiting-for-time outcome
    And does not sleep the worker thread

  Scenario: Replay before the due time remains deferred
    Given a checkpointed scheduled continuation is not yet due
    When the procedure replays before the due time
    Then the original scheduled continuation remains authoritative
    And Tactus exposes waiting-for-time again

  Scenario: Replay after the due time continues exactly once
    Given a checkpointed scheduled continuation is due
    When the host resumes the procedure
    Then Procedure.defer returns the completed continuation result
    And execution continues exactly once after the scheduled continuation

  Scenario: A changed request fails closed
    Given a scheduled continuation is already checkpointed
    When replay supplies a conflicting continuation key or time
    Then Tactus rejects the conflicting scheduled continuation
