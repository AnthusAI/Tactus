Feature: CLI info output
  The CLI should display procedure metadata for valid workflows and fail on invalid input.

  Scenario: CLI info displays procedure details for a valid file
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
    When I run "tactus info" on the file
    Then the command should succeed
    And the output should display procedure information

  Scenario: CLI info fails on invalid file
    Given a Lua DSL file with content:
      """
      this is not valid lua
      """
    When I run "tactus info" on the file
    Then the command should fail
