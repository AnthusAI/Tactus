Feature: Custom Prompts (return, error, status)
  As a workflow developer
  I want to customize return, error, and status prompts
  So that I can control how procedures communicate their results

  Background:
    Given a Tactus validation environment

  @spec_mismatch @prompts_not_used_at_runtime
  Scenario: Custom return_prompt
    # TODO: SPEC.md describes return_prompt (lines 165-175)
    # "Injected when the procedure completes successfully"
    # Current implementation stores return_prompt but doesn't use it at runtime
    # Fix in: tactus/core/runtime.py - inject return_prompt before final return
    Given a Lua DSL file with content:
      """
      return_prompt("Summarize your work concisely")
      
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })
      
      procedure(function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  @spec_mismatch @prompts_not_used_at_runtime
  Scenario: Custom error_prompt
    # TODO: SPEC.md describes error_prompt (lines 177-187)
    # "Injected when the procedure fails"
    # Current implementation stores error_prompt but doesn't use it at runtime
    # Fix in: tactus/core/runtime.py - inject error_prompt on exception
    Given a Lua DSL file with content:
      """
      error_prompt("Explain what went wrong and any partial progress")
      
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })
      
      procedure(function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  @spec_mismatch @prompts_not_used_at_runtime
  Scenario: Custom status_prompt
    # TODO: SPEC.md describes status_prompt (lines 189-199)
    # "Injected when a caller requests a status update (async procedures only)"
    # Current implementation stores status_prompt but doesn't use it at runtime
    # Fix in: tactus/core/runtime.py - inject status_prompt on status request
    Given a Lua DSL file with content:
      """
      status_prompt("Provide a brief progress update")
      
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })
      
      procedure(function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: All three custom prompts
    Given a Lua DSL file with content:
      """
      return_prompt("Summarize your work")
      error_prompt("Explain the error")
      status_prompt("Report progress")
      
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })
      
      procedure(function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Multi-line custom prompts
    Given a Lua DSL file with content:
      """
      return_prompt([[
        Summarize your work:
        - What was accomplished
        - Key findings
      ]])
      
      error_prompt([[
        Explain what went wrong:
        - What you were attempting
        - What failed
      ]])
      
      agent("worker", {
        provider = "openai",
        system_prompt = "Work",
        tools = {}
      })
      
      procedure(function()
        return { result = "done" }
      end)
      """
    When I validate the file
    Then validation should succeed
