Feature: IDE Server Management
  As a Tactus developer
  I want the IDE server to handle port conflicts gracefully
  So that I can run multiple instances without manual configuration

  Background:
    Given the Tactus IDE is installed

  Scenario: Starting IDE on default ports
    When I start the IDE with command "tactus ide"
    Then the backend should start on port 5001
    And the frontend should start on port 3000
    And the browser should open to "http://localhost:3000"
    And I should see "Backend port: 5001" in the output
    And I should see "Frontend port: 3000" in the output

  Scenario: Starting IDE when default backend port is occupied
    Given port 5001 is already in use
    When I start the IDE with command "tactus ide"
    Then the backend should start on the next available port
    And I should see "Backend port:" followed by a port number in the output
    And the frontend should connect to the detected backend port
    And the IDE should function normally

  Scenario: Starting IDE when default frontend port is occupied
    Given port 3000 is already in use
    When I start the IDE with command "tactus ide"
    Then the backend should start on port 5001
    And the frontend should start on the next available port
    And I should see a note about port 3000 being in use
    And I should see "Frontend port:" followed by a different port number
    And the browser should open to the detected frontend port

  Scenario: Starting IDE when both default ports are occupied
    Given port 5001 is already in use
    And port 3000 is already in use
    When I start the IDE with command "tactus ide"
    Then the backend should start on an available port
    And the frontend should start on an available port
    And I should see both ports in the output
    And the IDE should function normally

  Scenario: Running multiple IDE instances simultaneously
    Given I have started the IDE in terminal 1
    When I start the IDE in terminal 2 with command "tactus ide"
    Then terminal 1 should show "Backend port: 5001"
    And terminal 1 should show "Frontend port: 3000"
    And terminal 2 should show a different backend port
    And terminal 2 should show a different frontend port
    And both IDE instances should function independently

  Scenario: Starting IDE with custom backend port
    When I start the IDE with command "tactus ide --port 5555"
    Then the backend should start on port 5555
    And I should see "Backend port: 5555" in the output

  Scenario: Starting IDE with custom backend port that is occupied
    Given port 5555 is already in use
    When I start the IDE with command "tactus ide --port 5555"
    Then the backend should start on the next available port after 5555
    And I should see "Backend port:" followed by a port number in the output

  Scenario: Starting IDE without opening browser
    When I start the IDE with command "tactus ide --no-browser"
    Then the backend should start on port 5001
    And the frontend should start on port 3000
    And the browser should NOT open automatically
    And I should see the frontend URL in the output

  Scenario: Electron app detects backend ports
    Given I start the IDE with command "tactus ide --no-browser"
    And the backend starts on port 5001
    And the frontend starts on port 3000
    When I start the Electron app
    Then the Electron app should detect port 5001 from backend output
    And the Electron app should detect port 3000 from frontend output
    And the Electron window should load "http://localhost:3000"

  Scenario: Electron app handles port conflicts
    Given port 5001 is already in use
    When I start the Electron app
    Then the Electron app should spawn "tactus ide --no-browser"
    And the backend should find an available port
    And the Electron app should parse the new port from output
    And the Electron window should load the correct frontend URL

  Scenario: IDE server graceful shutdown
    Given the IDE is running
    When I press Ctrl+C
    Then the backend server should stop
    And the frontend server should stop
    And all ports should be released
    And I should see "Press Ctrl+C to stop the IDE" before shutdown

  Scenario: IDE server timeout handling
    When I start the IDE
    And the backend fails to start within 30 seconds
    Then I should see an error message
    And the IDE should exit with a non-zero code
    And no ports should remain occupied

  Scenario: Port detection race condition
    When I start the IDE
    Then the backend port should be detected before frontend starts
    And the frontend should use the detected backend port
    And there should be no connection errors

  Scenario: IDE server health check
    Given the IDE is running on port 5001
    When I send a GET request to "http://localhost:5001/health"
    Then I should receive a 200 OK response
    And the response should contain "status": "ok"
    And the response should contain "service": "tactus-ide-backend"

