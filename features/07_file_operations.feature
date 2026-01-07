Feature: File Operations
  As a workflow developer
  I want to read and write files
  So that workflows can persist and process data

  Background:
  Given a Tactus workflow environment
  And the file primitive is initialized
  And a temporary workspace directory

  Scenario: Reading a text file
  Given a file "input.txt" with content:
  """
  Hello, World!
  This is a test.
  """
  When I read the file "input.txt"
  Then the content should match the original text

  Scenario: Writing to a file
  When I write "Generated output" to file "output.txt"
  Then the file "output.txt" should exist
  And its content should be "Generated output"

  Scenario: Appending to an existing file
  Given a file "log.txt" with content "Line 1"
  When I append "Line 2" to file "log.txt"
  Then the file should contain both lines:
  """
  Line 1
  Line 2
  """

  Scenario: Reading JSON data
  Given a file "data.json" with content:
  """
  {"name": "Alice", "age": 30}
  """
  When I read JSON from "data.json"
  Then I should have a parsed object
  And the object should have field "name" with value "Alice"

  Scenario: Writing JSON data
  Given a data structure:
  | field | value |
  | name  | Bob  |
  | age  | 25  |
  When I write it as JSON to "output.json"
  Then the file should contain valid JSON
  And reading it back should give the same structure

  Scenario: File not found handling
  When I try to read a non-existent file "missing.txt"
  Then a file not found error should be raised
  And the workflow can handle the error gracefully

  Scenario: Processing multiple files
  Given files in directory "inputs/":
  | filename  | content  |
  | file1.txt  | Content 1  |
  | file2.txt  | Content 2  |
  | file3.txt  | Content 3  |
  When I process all files in "inputs/"
  Then each file should be read and processed
  And results should be collected
