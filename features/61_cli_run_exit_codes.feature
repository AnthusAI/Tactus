Feature: CLI run exit codes

  Scenario: CLI run returns non-zero exit code on runtime failure
    Given a Lua DSL file with content:
      """
      return does_not_exist()
      """
    When I run "tactus run --no-sandbox" on the file
    Then the command should fail
    And the output should show "Workflow failed"
