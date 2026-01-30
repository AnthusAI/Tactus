Feature: Formatting
  Formatting produces stable, canonical Lua DSL text.

  Scenario: Formatting enforces 2-space semantic indentation
    Given a formatting environment
    And a Lua DSL file with formatting issues
    When I run "tactus format" on the file
    Then the format command should succeed
    And the file should be formatted with 2-space indentation

  Scenario: Formatting is idempotent
    Given a formatting environment
    And a Lua DSL file with formatting issues
    When I run "tactus format" on the file
    And I run "tactus format" on the file
    Then the format command should succeed
    And the file should be unchanged by the second run

  Scenario: Check mode detects required changes
    Given a formatting environment
    And a Lua DSL file with formatting issues
    When I run "tactus format --check" on the file
    Then the format command should fail

  Scenario: Check mode passes when formatted
    Given a formatting environment
    And a Lua DSL file with formatting issues
    When I run "tactus format" on the file
    And I run "tactus format --check" on the file
    Then the format command should succeed

  Scenario: Formatting to stdout does not modify the file
    Given a formatting environment
    And a Lua DSL file with formatting issues
    When I run "tactus format --stdout" on the file
    Then the format command should succeed
    And the formatted output should be printed
    And the file should be unchanged by the format output

  Scenario: Formatting indents Specifications content
    Given a formatting environment
    And a Lua DSL file with Specifications content needing indentation
    When I run "tactus format" on the file
    Then the format command should succeed
    And the Specifications content should be indented by 2 spaces

  Scenario: Formatting rejects non-Lua files
    Given a formatting environment
    And a non-Lua file
    When I run "tactus format" on the file
    Then the format command should fail

  Scenario: Formatting fails when the file is missing
    Given a formatting environment
    And a missing Lua file path
    When I run "tactus format" on the file
    Then the format command should fail
    And the output should show "not found"
