Feature: CLI run exit codes

  Scenario: CLI run returns non-zero exit code on runtime failure
    Given a Lua DSL file with content:
      """
      return does_not_exist()
      """
    When I run "tactus run --no-sandbox" on the file
    Then the command should fail
    And the output should show "Workflow failed"

  Scenario: CLI run rejects invalid log level
    Given a Lua DSL file with content:
      """
      main = Procedure {
        output = {
          ok = field.boolean{required = true}
        },
        function(input)
          return { ok = true }
        end
      }
      """
    When I run "tactus run --no-sandbox --log-level nope" on the file
    Then the command should fail

  Scenario: CLI run rejects invalid log format
    Given a Lua DSL file with content:
      """
      main = Procedure {
        output = {
          ok = field.boolean{required = true}
        },
        function(input)
          return { ok = true }
        end
      }
      """
    When I run "tactus run --no-sandbox --log-format nope" on the file
    Then the command should fail
