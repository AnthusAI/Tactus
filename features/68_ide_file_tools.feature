Feature: IDE File Tools
  As an IDE user
  I want safe file operations
  So that the assistant can read and edit workspace files safely

  Background:
    Given an IDE workspace with a sample file

  Scenario: Read and list files
    When I read the sample file
    Then I should receive the file contents
    And I can list files in the workspace

  Scenario: Search files by pattern
    When I search for files with pattern "*.tac"
    Then I should see the sample file in results

  Scenario: Edit file content
    When I replace "hello" with "hi" in the sample file
    Then the file should contain "hi"

  Scenario: Copy and move files
    When I copy the sample file to "copies/sample_copy.tac"
    And I move the sample file to "moved/sample_moved.tac"
    Then the copied file should exist
    And the moved file should exist

  Scenario: Delete file
    When I delete the copied file
    Then the copied file should be removed

  Scenario: View files with line numbers
    When I view the moved file
    Then the view should include line numbers

  Scenario: View directory listing
    When I view the workspace directory
    Then the directory view should include the moved file
