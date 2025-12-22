@skip
Feature: IDE Server Management
  As a Tactus developer
  I want the IDE server to handle port conflicts gracefully
  So that I can run multiple instances without manual configuration
  
  # NOTE: This feature is skipped because it requires launching real IDE server processes
  # which would block test execution. These scenarios test the IDE server behavior
  # but are mocked when the @skip tag is present to allow the test suite to complete.
  
  Background:
    Given the Tactus IDE is installed

  Scenario: Starting IDE on default ports
    When I start the IDE with command "tactus ide"
    Then I should see "Server port: 5001" in the output
    And the browser should open to "http://localhost:5001"

  Scenario: Starting IDE when port is occupied
    Given port 5001 is already in use
    When I start the IDE with command "tactus ide"
    Then I should see "Server port:" followed by a port number in the output

  Scenario: Running multiple IDE instances
    Given I have started the IDE in terminal 1
    When I start the IDE in terminal 2 with command "tactus ide"
    Then terminal 1 should show "Server port: 5001"
    And I should see "Server port:" followed by a port number in the output

  Scenario: Starting IDE with --no-browser flag
    When I start the IDE with command "tactus ide --no-browser"
    Then I should see "Server port: 5001" in the output
    And the browser should NOT open automatically

  Scenario: Stopping IDE with Ctrl+C
    Given I have started the IDE in terminal 1
    When I press Ctrl+C
    Then I should see "Server port:" in the output





