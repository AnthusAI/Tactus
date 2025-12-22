# Tactus BDD Testing Framework

First-class Gherkin-style BDD testing integrated into the Tactus DSL.

## Overview

The Tactus BDD Testing Framework allows you to write behavior-driven tests directly in your procedure files using Gherkin syntax. Tests are executed using Behave under the hood, with full support for:

- **Natural language specifications** - Write tests in plain English using Gherkin
- **Built-in step library** - Comprehensive steps for Tactus primitives (tools, stages, state, etc.)
- **Custom steps** - Define your own steps in Lua for advanced assertions
- **Parallel execution** - Run scenarios in parallel for fast feedback
- **Consistency evaluation** - Run tests multiple times to measure reliability
- **Structured results** - All results are Pydantic models, no text parsing

## Quick Start

### 1. Add Specifications to Your Procedure

```lua
-- procedure.tac
name("my_procedure")
version("1.0.0")

agent("worker", {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "Do the work",
  tools = {"search", "done"}
})

procedure(function()
  repeat
    Worker.turn()
  until Tool.called("done")
end)

-- Add BDD specifications
specifications([[
Feature: My Procedure

  Scenario: Worker completes task
    Given the procedure has started
    When the worker agent takes turns
    Then the search tool should be called
    And the done tool should be called
    And the procedure should complete successfully
]])
```

### 2. Run Tests

```bash
# Run all scenarios once
tactus test procedure.tac

# Run specific scenario
tactus test procedure.tac --scenario "Worker completes task"

# Run without parallel execution
tactus test procedure.tac --no-parallel
```

### 3. Evaluate Consistency

```bash
# Run each scenario 10 times to measure consistency
tactus test procedure.tac --runs 10

# Run with more iterations
tactus test procedure.tac --runs 50

# Evaluate specific scenario
tactus test procedure.tac --scenario "Worker completes task" --runs 20
```

## Built-in Steps

The framework provides a comprehensive library of built-in steps:

### Tool Steps

```gherkin
Then the search tool should be called
Then the search tool should not be called
Then the search tool should be called at least 3 times
Then the search tool should be called exactly 2 times
Then the search tool should be called with query=test
```

### Stage Steps

```gherkin
Given the procedure has started
Then the stage should be processing
Then the stage should transition from planning to executing
Given we are in stage complete
```

### State Steps

```gherkin
Then the state count should be 5
Then the state error should exist
Then the state should contain results
```

### Completion Steps

```gherkin
Then the procedure should complete successfully
Then the procedure should fail
Then the stop reason should be done
Then the stop reason should contain timeout
```

### Iteration Steps

```gherkin
Then the total iterations should be less than 10
Then the total iterations should be between 5 and 15
Then the agent should take at least 3 turns
```

### Parameter Steps

```gherkin
Given the topic parameter is quantum computing
Then the agent's context should include quantum computing
```

### Agent Steps

```gherkin
When the worker agent takes turns
When the procedure runs
```

## Custom Steps

Define custom steps in Lua for advanced assertions:

```lua
-- Custom step definition
step("the research quality is high", function()
  local results = State.get("research_results")
  assert(#results > 5, "Should have at least 5 results")
  assert(results[1].quality == "high", "First result should be high quality")
end)

-- Use in specifications
specifications([[
Feature: Research Quality

  Scenario: High quality research
    Given the procedure has started
    When the procedure runs
    Then the research quality is high
]])
```

## Evaluation Metrics

The `evaluate` command runs scenarios multiple times and provides:

- **Success Rate** - Percentage of runs that passed
- **Mean Duration** - Average execution time
- **Standard Deviation** - Timing consistency
- **Consistency Score** - How often runs produce identical step outcomes (0.0 to 1.0)
- **Flakiness Detection** - Identifies scenarios with inconsistent results

Example output:

```
Scenario: Agent completes research
  Success Rate: 90% (9/10)
  Duration: 1.23s (±0.15s)
  Consistency: 90%
  ⚠️  FLAKY - Inconsistent results detected
```

## Parser Warnings

The Tactus validator will warn if your procedure has no specifications:

```bash
$ tactus validate procedure.tac

⚠ Warning: No specifications defined - consider adding BDD tests using specifications([[...]])
```

## Note on Evaluations

This framework is for **testing logic** (BDD). If you want to evaluate **LLM output quality** using datasets and metrics (Pydantic Evals), see the main [README](../../README.md#evaluations-testing-agent-intelligence) and use the `tactus eval` command.

## Architecture

```
Tactus Procedure (.tac)
  └─ specifications([[ Gherkin text ]])
  └─ step("custom step", function() ... end)
           ↓
    Gherkin Parser (gherkin-official)
           ↓
    Feature/Scenario/Step AST
           ↓
    Step Matcher (built-in + custom steps)
           ↓
    Behave Integration Layer
      ├─ Generate .feature files
      ├─ Generate step_definitions.py
      └─ Run via Behave Runner API
           ↓
    Parallel Execution (multiprocessing)
           ↓
    Structured Results (Pydantic models)
           ↓
    CLI Output / IDE Display / Log Events
```

## API Usage

You can also use the testing framework programmatically:

```python
from pathlib import Path
from tactus.testing import TactusTestRunner, TactusEvaluationRunner

# Run tests
runner = TactusTestRunner(Path("procedure.tac"))
runner.setup(gherkin_text)
result = runner.run_tests(parallel=True)

print(f"Passed: {result.passed_scenarios}/{result.total_scenarios}")

# Run evaluation
evaluator = TactusEvaluationRunner(Path("procedure.tac"))
evaluator.setup(gherkin_text)
eval_results = evaluator.evaluate_all(runs=10, parallel=True)

for result in eval_results:
    print(f"{result.scenario_name}: {result.success_rate:.1%} success rate")
```

## IDE Integration

Test and evaluation results are emitted as structured log events for IDE display:

- `TestStartedEvent`
- `TestCompletedEvent`
- `TestScenarioStartedEvent`
- `TestScenarioCompletedEvent`
- `EvaluationStartedEvent`
- `EvaluationCompletedEvent`
- `EvaluationScenarioStartedEvent`
- `EvaluationScenarioCompletedEvent`
- `EvaluationProgressEvent`

All events are Pydantic models that can be serialized to JSON for display in the IDE's execution panel.

## Dependencies

The testing framework requires:

- `behave>=1.2.6` - BDD test execution
- `gherkin-official>=28.0.0` - Gherkin parsing

These are automatically installed with Tactus.

## Examples

See `examples/with-bdd-tests.tac` for a complete example with:
- Multiple scenarios
- Custom steps
- Evaluation configuration
- All major step types







