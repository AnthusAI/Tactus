Feature: Prompt Templates
  As a workflow developer
  I want to define reusable prompt templates
  So that I can maintain consistent prompts across agents

  Background:
    Given a Tactus validation environment

  Scenario: Simple prompt template
    Given a Lua DSL file with content:
      """
      prompt("greeting", "Hello, {input.name}! How can I help you today?")

      agent("worker", {
        provider = "openai",
        system_prompt = prompts.greeting,
        tools = {}
      })

      procedure({
        input = {
          name = {
            type = "string",
            default = "User"
          }
        }
      }, function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Multiple prompt templates
    Given a Lua DSL file with content:
      """
      prompt("intro", "Welcome to the system")
      prompt("task", "Please complete the following task")
      prompt("outro", "Thank you for using our service")

      agent("worker", {
        provider = "openai",
        system_prompt = prompts.intro,
        tools = {}
      })

      procedure(function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Multi-line prompt template
    Given a Lua DSL file with content:
      """
      prompt("detailed", [[
        You are a helpful assistant.
        Your goal is to help the user.
        Be concise and accurate.
      ]])

      agent("worker", {
        provider = "openai",
        system_prompt = prompts.detailed,
        tools = {}
      })

      procedure(function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Prompt template with input substitution
    Given a Lua DSL file with content:
      """
      prompt("task_prompt", "Research the topic: {input.topic}")

      agent("researcher", {
        provider = "openai",
        system_prompt = prompts.task_prompt,
        tools = {}
      })

      procedure({
        input = {
          topic = {
            type = "string",
            required = true
          }
        }
      }, function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed
