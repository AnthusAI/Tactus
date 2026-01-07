Feature: Logging
  As a workflow developer
  I want to log workflow events and data
  So that I can debug and monitor execution

  Background:
  Given a Tactus workflow environment
  And the log primitive is initialized

  Scenario: Logging at different levels
  When I log "Starting workflow" at INFO level
  And I log "Debug information" at DEBUG level
  And I log "Warning message" at WARN level
  And I log "Error occurred" at ERROR level
  Then all messages should be recorded
  And each should have the correct level

  Scenario: Structured logging with context
  When I log with context:
  | field  | value  |
  | user_id  | 12345  |
  | action  | process_data  |
  | status  | success  |
  Then the log entry should include all context fields
  And it should be queryable by any field

  Scenario: Log filtering by level
  Given log level is set to WARN
  When I log "Debug info" at DEBUG level
  And I log "Info message" at INFO level
  And I log "Warning" at WARN level
  Then only WARN and higher should be captured
  And DEBUG and INFO should be filtered out

  Scenario: Logging workflow progress
  Given a multi-step workflow
  When I log progress at each step
  Then I should be able to track workflow execution
  And see which steps completed successfully

  Scenario: Logging exceptions
  When an error occurs in the workflow
  And I log the exception with traceback
  Then the log should include:
  | field  |
  | error_type  |
  | error_message|
  | stack_trace  |
  | timestamp  |

  Scenario: Custom log formatters
  Given a custom formatter that outputs JSON
  When I log messages
  Then each log entry should be valid JSON
  And include timestamp, level, and message

  Scenario: Log aggregation across workflow runs
  Given multiple executions of the same workflow
  When I query logs for procedure_id "research_123"
  Then I should see all log entries
  And they should be chronologically ordered

  Scenario: Performance logging
  When I log operation start time
  And execute an operation
  And log operation end time
  Then I can calculate operation duration
  And identify performance bottlenecks
