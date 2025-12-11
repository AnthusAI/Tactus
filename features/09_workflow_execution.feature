Feature: Workflow Execution
  As a workflow developer
  I want to run complete workflows from YAML definitions
  So that I can orchestrate complex multi-step processes

  Background:
    Given a Tactus runtime is initialized

  Scenario: Running a simple linear workflow
    Given a workflow YAML:
      """
      name: simple_workflow
      steps:
        - id: step1
          action: state.set
          params:
            key: result
            value: completed
      """
    When I execute the workflow
    Then the workflow should complete successfully
    And state "result" should equal "completed"

  Scenario: Workflow with parameters
    Given a workflow that accepts parameters
    When I execute with parameters:
      | parameter | value         |
      | topic     | AI research   |
      | depth     | detailed      |
    Then the workflow should use the provided parameters
    And state should reflect the parameter values

  Scenario: Multi-step workflow with dependencies
    Given a workflow YAML:
      """
      name: multi_step
      steps:
        - id: fetch_data
          action: tool.call
          params:
            tool: get_data
        - id: process_data
          action: agent.call
          params:
            prompt: "Analyze: {{ fetch_data.result }}"
        - id: save_result
          action: file.write
          params:
            path: output.txt
            content: "{{ process_data.result }}"
      """
    When I execute the workflow
    Then each step should execute in order
    And each step should receive outputs from previous steps
    And the final result should be saved to file

  Scenario: Workflow with error handling
    Given a workflow with error handlers
    When a step fails with an error
    Then the error handler should be invoked
    And the workflow should handle the error gracefully
    And execution should continue or halt as configured

  Scenario: Conditional workflow paths
    Given a workflow with conditional branches
    When I execute with state "mode" set to "production"
    Then the production path should execute
    And the development path should be skipped

  Scenario: Parallel step execution
    Given a workflow with parallel steps:
      """
      name: parallel_workflow
      steps:
        - id: parallel_group
          action: parallel
          steps:
            - id: task1
              action: agent.call
              params:
                prompt: "Task 1"
            - id: task2
              action: agent.call
              params:
                prompt: "Task 2"
            - id: task3
              action: agent.call
              params:
                prompt: "Task 3"
      """
    When I execute the workflow
    Then all tasks should execute concurrently
    And the workflow should wait for all to complete
    And total time should be less than sequential execution

  Scenario: Workflow timeout
    Given a workflow with timeout 30 seconds
    When I execute a long-running workflow
    And it exceeds 30 seconds
    Then the workflow should be terminated
    And a timeout error should be raised

  Scenario: Workflow resume after interruption
    Given a workflow that was interrupted at step 3
    And checkpoints exist for steps 1 and 2
    When I resume the workflow
    Then steps 1 and 2 should be skipped
    And execution should continue from step 3
    And state should be restored from checkpoints
