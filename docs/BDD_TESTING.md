# Gherkin BDD Testing in Tactus

## Overview

Tactus includes first-class support for behavior-driven testing using Gherkin syntax. Write natural language specifications directly in your procedure files and run them with `tactus test` and `tactus evaluate` commands.

## Why BDD Testing in Tactus?

Agent workflows are inherently non-deterministic. Unlike traditional code, the same procedure can produce different results on different runs due to:
- LLM response variability
- Tool call ordering
- State management decisions
- Timing and iteration counts

**BDD testing in Tactus addresses this by:**
1. **Natural language specs** - Describe expected behavior in plain English
2. **Built-in steps** - Test Tactus primitives (tools, state) without writing code
3. **Consistency evaluation** - Run tests multiple times to measure reliability
4. **Flakiness detection** - Identify unreliable scenarios automatically
5. **Hybrid execution** - Support both real LLM execution and mocked tools

## Execution Modes

Tactus BDD testing supports two execution modes:

### Real Mode (Default)

Executes procedures with actual LLM calls and tool execution:

```bash
tactus test procedure.tac
```

**Characteristics:**
- Requires API keys (OPENAI_API_KEY, etc.)
- Makes real LLM calls
- Slower execution
- Costs money
- Non-deterministic results
- Tests real behavior end-to-end

**Use when:**
- Validating actual LLM behavior
- Integration testing
- Measuring real-world consistency
- Acceptance testing

### Mock Mode

Executes procedures with mocked tool responses:

```bash
tactus test procedure.tac --mock
```

**Characteristics:**
- No API keys required
- No LLM calls made
- Fast execution (seconds)
- Free
- Deterministic results
- Tests workflow logic

**Use when:**
- Developing tests
- CI/CD pipelines
- Testing workflow logic
- Rapid iteration
- Cost-sensitive environments

### Custom Mock Configuration

Provide custom mock responses via JSON file:

```bash
tactus test procedure.tac --mock-config mocks.json
```

**mocks.json:**
```json
{
  "done": {
    "status": "complete",
    "message": "Task finished"
  },
  "search": {
    "results": ["result1", "result2", "result3"]
  }
}
```

Mock responses can be:
- **Static values** - Same response every time
- **Callable functions** - Dynamic responses based on arguments (in code)

## How Mock Mode Works

When you run `tactus test --mock`:

1. **TactusTestContext** creates `MockToolRegistry` with configured mocks
2. **MockedToolPrimitive** is created and injected into `TactusRuntime`
3. **Runtime** is configured with `skip_agents=True`
4. **During execution:**
   - Tool calls return mocked responses from registry
   - Agent turns use `MockAgentPrimitive` (calls done tool automatically)
   - State primitives work normally
   - No LLM calls are made
5. **After execution:**
   - Primitives are captured from runtime
   - Test steps access captured primitive states
6. **Assertions:**
   - `tool_called()` checks MockedToolPrimitive
   - `state_get()` checks StatePrimitive

This allows testing workflow logic without LLM calls, making tests:
- **Fast** - Seconds instead of minutes
- **Free** - No API costs
- **Deterministic** - Same results every time
- **Offline** - No network required

## Mocking in Procedures

While the `--mock` flag provides basic mocking, you can define sophisticated mock behavior directly in your procedure files using the `Mocks {}` primitive. This gives you fine-grained control over tool responses during testing.

### The Mocks {} Primitive

Define mocks at the top level of your procedure file:

```lua
-- Define mock configurations for tools
Mocks {
    tool_name = {
        returns = {...},        -- Static: same response every time
        temporal = {...},       -- Temporal: different values per call
        conditional = {...}     -- Conditional: values based on input
    }
}
```

### Static Mocking

Static mocks always return the same value:

```lua
Mocks {
    weather = {
        returns = {
            temperature = 72,
            conditions = "Sunny",
            location = "San Francisco"
        }
    },
    stock_price = {
        returns = {
            symbol = "AAPL",
            price = 150.25,
            change = 2.5
        }
    }
}
```

**Use when:** Tool behavior should be constant and predictable.

### Temporal Mocking

Temporal mocks return different values on successive calls:

```lua
Mocks {
    get_counter = {
        temporal = {
            {value = 1, message = "First call"},
            {value = 2, message = "Second call"},
            {value = 3, message = "Third call"},
            {value = 999, message = "Fallback for subsequent calls"}
        }
    },
    check_status = {
        temporal = {
            {status = "pending", progress = 0},
            {status = "in_progress", progress = 50},
            {status = "completed", progress = 100}
        }
    }
}
```

**Behavior:**
- First call returns first item
- Second call returns second item
- After exhausting the list, the last item is used for all subsequent calls

**Use when:** Testing retry logic, polling, or stateful tool interactions.

### Conditional Mocking

Conditional mocks return different values based on input parameters:

```lua
Mocks {
    translate = {
        conditional = {
            {when = {text = "hello"}, returns = {translation = "hola", language = "Spanish"}},
            {when = {text = "goodbye"}, returns = {translation = "adiós", language = "Spanish"}},
            {when = {text = "thank you"}, returns = {translation = "gracias", language = "Spanish"}}
        }
    },
    calculate = {
        conditional = {
            {when = {operation = "add", x = 5, y = 3}, returns = {result = 8}},
            {when = {operation = "multiply", x = 4, y = 7}, returns = {result = 28}}
        }
    }
}
```

**Matching behavior:**
- Exact value matching by default
- String matching supports special prefixes:
  - `contains:` - substring check
  - `startswith:` - prefix check
  - `endswith:` - suffix check

**Use when:** Tool behavior depends on specific inputs.

### Complete Mocking Example

Here's a complete example combining mocks with BDD specifications:

```lua
-- Tool definitions
done = tactus.done

weather = Tool {
    description = "Get current weather",
    input = { location = field.string{} },
    function(input)
        return {temperature = 0}  -- Won't be called when mocked
    end
}

-- Define mocks
Mocks {
    weather = {
        returns = {
            temperature = 72,
            conditions = "Sunny"
        }
    }
}

-- Agent using mocked tools
assistant = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You help with weather queries.",
    tools = {weather, done}
}

-- Procedure
Procedure {
    output = {
        result = field.string{required = true}
    },
    function(input)
        assistant({
            message = "Get the weather in San Francisco"
        })

        while not done.called() do
            assistant()
        end

        return {result = "Weather retrieved"}
    end
}

-- BDD Specifications
Specification([[
Feature: Weather Query with Mocking

  Scenario: Weather tool returns mocked data
    Given the procedure has started
    When the procedure runs
    Then the weather tool should be called
    And the done tool should be called
    And the procedure should complete successfully
]])
```

### Mocking DSPy Modules

DSPy modules are mocked using the same `Mocks {}` primitive as tools. Simply specify the module name as the key:

```lua
-- Configure the real LM for production
LM("openai/gpt-4o-mini")

-- Create your module
qa = Module {
    signature = "question -> answer",
    strategy = "predict"
}

-- Configure mock responses for testing
Mocks {
    qa = {
        -- Static mock: same response every time
        returns = {answer = "Mario Götze"}
    }
}
```

**Temporal mocking** for modules that are called multiple times:

```lua
Mocks {
    qa = {
        temporal = {
            {answer = "First response"},
            {answer = "Second response"},
            {answer = "Third response"}
        }
    }
}
```

**Conditional mocking** based on input:

```lua
Mocks {
    qa = {
        conditional = {
            {when = {question = "What is 2+2?"}, returns = {answer = "4"}},
            {when = {question = "contains:capital"}, returns = {answer = "Berlin"}}
        }
    }
}
```

**Unified mocking** for both tools and modules:

```lua
Mocks {
    -- Mock a tool
    weather = {
        returns = {temperature = "72°F", condition = "sunny"}
    },
    -- Mock a DSPy module
    qa = {
        returns = {answer = "Mario Götze"}
    }
}
```

**Note:** Mocks only activate when running in mock mode (`tactus test --mock`). In real mode, actual tools and LMs are used.

See `examples/70-mocking-static.tac`, `examples/71-mocking-temporal.tac`, and `examples/72-mocking-conditional.tac` for tool mocking examples, and `examples/80-dspy-predict-basic.tac` through `examples/87-dspy-history.tac` for DSPy module mocking examples.

## Quick Example

```lua
done = tactus.done
search = mcp.brave_search.search

researcher = Agent {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "Research: {input.topic}",
  tools = {search, done}
}

Procedure {
  function(input)
    repeat
      researcher()
    until done.called()
  end
}

-- BDD Specifications
Specification([[
Feature: Research Task

  Scenario: Agent completes research
    Given the procedure has started
    When the researcher agent takes turns
    Then the search tool should be called
    And the done tool should be called
    And the procedure should complete successfully
]])
```

**Run tests:**
```bash
tactus test procedure.lua
```

**Evaluate consistency:**
```bash
tactus evaluate procedure.lua --runs 10
```

## Built-in Steps Reference

### Inline mocking (recommended)

In addition to `Mocks {}`, you can declare mocks directly inside Gherkin scenarios so the mocks live next to the behavior they support:

```gherkin
And the agent "researcher" responds with "Mocked response"
And the tool "search" returns {"results": ["a", "b"]}
```

### Fuzzy Output Steps

For scalar outputs (where `result.output` is a string), you can use deterministic fuzzy matching. This is useful for real-model runs where exact phrasing can vary.

```gherkin
Then the output should fuzzy match "Hello world" with threshold 0.9
Then the output should fuzzy match any of ["hello", "hi", "hey"] with threshold 0.9
```

Defaults:
- Case-insensitive (compares lowercased text)
- Punctuation-insensitive (strips punctuation)
- Collapses whitespace

### Tool Steps

Test tool usage patterns:

```gherkin
Then the search tool should be called
Then the search tool should not be called
Then the search tool should be called at least 3 times
Then the search tool should be called exactly 2 times
Then the search tool should be called with query=test
```

### State Steps

Test state management:

```gherkin
Then the state count should be 5
Then the state error should exist
Then the state should contain results
```

### Completion Steps

Test procedure completion:

```gherkin
Then the procedure should complete successfully
Then the procedure should fail
Then the stop reason should be done
Then the stop reason should contain timeout
```

### Iteration Steps

Test execution characteristics:

```gherkin
Then the total iterations should be less than 10
Then the total iterations should be between 5 and 15
Then the agent should take at least 3 turns
```

### Parameter Steps

Test parameter handling:

```gherkin
Given the topic parameter is quantum computing
Then the agent's context should include quantum computing
```

### Agent Steps

Trigger procedure execution:

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

The `tactus evaluate` command runs scenarios multiple times and provides:

### Success Rate
Percentage of runs that passed all steps.

```
Success Rate: 90% (9/10)
```

### Timing Statistics
Mean, median, and standard deviation of execution time.

```
Duration: 1.23s (±0.15s)
```

### Consistency Score
Measures how often runs produce identical step-by-step behavior (0.0 to 1.0).

```
Consistency: 90%
```

A consistency score of 1.0 means all runs had identical step outcomes. Lower scores indicate variability in behavior.

### Flakiness Detection
Automatically identifies scenarios that sometimes pass and sometimes fail.

```
⚠️  FLAKY - Inconsistent results detected
```

Flaky scenarios indicate non-deterministic behavior that may need investigation.

## CLI Commands

### tactus test

Run each scenario once and report pass/fail:

```bash
# Run all scenarios (real mode)
tactus test procedure.tac

# Run with mocked tools (fast, deterministic)
tactus test procedure.tac --mock

# Run with custom mock config
tactus test procedure.tac --mock-config mocks.json

# Run specific scenario
tactus test procedure.tac --scenario "Agent completes research"

# Pass parameters
tactus test procedure.tac --param topic="AI" --param count=5

# Run sequentially (no parallel)
tactus test procedure.tac --no-parallel

# Verbose output
tactus test procedure.tac -v
```

**Output:**
```
Feature: Research Task
  ✓ Scenario: Agent completes research (1.2s)
  ✗ Scenario: Agent handles errors (0.8s)
    Failed: Then the error should be logged
    
2 scenarios (1 passed, 1 failed)
```

### tactus evaluate

Run each scenario multiple times to measure consistency:

```bash
# Evaluate with 10 runs per scenario (real mode)
tactus evaluate procedure.tac --runs 10

# Evaluate with mocked tools (fast, deterministic)
tactus evaluate procedure.tac --runs 50 --mock

# Evaluate with custom mock config
tactus evaluate procedure.tac --runs 20 --mock-config mocks.json

# Evaluate with custom workers
tactus evaluate procedure.tac --runs 50 --workers 10

# Evaluate specific scenario
tactus evaluate procedure.tac --scenario "Agent completes research" --runs 20

# Pass parameters
tactus evaluate procedure.tac --runs 10 --param topic="AI"

# Sequential evaluation (no parallel)
tactus evaluate procedure.tac --runs 10 --no-parallel
```

**Output:**
```
Scenario: Agent completes research
  Success Rate: 90% (9/10)
  Duration: 1.23s (±0.15s)
  Consistency: 90%
  ⚠️  FLAKY - Inconsistent results detected

Scenario: Agent handles errors
  Success Rate: 100% (10/10)
  Duration: 0.82s (±0.08s)
  Consistency: 100%
```

## Parser Warnings

The Tactus validator warns if procedures have no specifications:

```bash
$ tactus validate procedure.lua

⚠ Warning: No specifications defined - consider adding BDD tests using specifications([[...]])
```

This encourages test-driven development and helps ensure procedures are well-tested.

## Architecture

### How It Works

1. **Parse Gherkin** - Extract `specifications([[...]])` from procedure file
2. **Generate .feature files** - Convert to Behave-compatible format
3. **Generate step definitions** - Create Python step_definitions.py
4. **Execute with Behave** - Run via Behave's programmatic API
5. **Parallel execution** - Use multiprocessing for performance
6. **Structured results** - Convert Behave objects to Pydantic models

### No Text Parsing

All results are structured Pydantic models - no stdout/stderr parsing required:

```python
from tactus.testing import TactusTestRunner

runner = TactusTestRunner(Path("procedure.lua"))
runner.setup(gherkin_text)
result = runner.run_tests()

# result is a TestResult Pydantic model
print(f"Passed: {result.passed_scenarios}/{result.total_scenarios}")
for feature in result.features:
    for scenario in feature.scenarios:
        print(f"{scenario.name}: {scenario.status}")
```

### IDE Integration

Test and evaluation results are emitted as structured log events:

- `TestStartedEvent`
- `TestCompletedEvent`
- `TestScenarioStartedEvent`
- `TestScenarioCompletedEvent`
- `EvaluationStartedEvent`
- `EvaluationCompletedEvent`
- `EvaluationScenarioStartedEvent`
- `EvaluationScenarioCompletedEvent`
- `EvaluationProgressEvent`

These events can be displayed in the IDE's execution panel alongside normal procedure logs.

## Best Practices

### 1. Test Key Behaviors

Focus on testing the important behaviors of your procedure:

```gherkin
Scenario: Agent completes task successfully
  Given the procedure has started
  When the agent takes turns
  Then the done tool should be called
  And the procedure should complete successfully
```

### 2. Test Tool Usage

Ensure tools are called appropriately:

```gherkin
Scenario: Tool usage patterns
  Given the procedure has started
  When the agent takes turns
  Then the search tool should be called at least once
  And the search tool should be called with query=test
  And the done tool should be called exactly once
```

### 4. Use Evaluation for Reliability

Run evaluations to measure consistency:

```bash
tactus evaluate procedure.lua --runs 20
```

Look for:
- Success rates below 90% (may indicate reliability issues)
- Low consistency scores (indicates non-deterministic behavior)
- Flaky scenarios (sometimes pass, sometimes fail)

### 5. Custom Steps for Complex Assertions

Use custom steps when built-in steps aren't enough:

```lua
step("the results meet quality standards", function()
  local results = State.get("results")
  local high_quality = 0
  for _, result in ipairs(results) do
    if result.score > 0.8 then
      high_quality = high_quality + 1
    end
  end
  assert(high_quality / #results > 0.7, "At least 70% should be high quality")
end)
```

## Troubleshooting

### "No specifications found"

Make sure you've added the `specifications([[...]])` call to your procedure file.

### "Step not implemented"

The step text doesn't match any built-in or custom steps. Check:
1. Step text matches a built-in pattern
2. Custom step is registered with `step("text", function)`
3. Spelling and capitalization (matching is case-insensitive)

### Flaky Tests

If evaluation shows flaky scenarios:
1. Check for non-deterministic code between checkpoints
2. Verify tool mocks are consistent
3. Consider using `Step.run()` to checkpoint non-deterministic operations
4. Review LLM temperature settings (lower = more deterministic)

### Performance Issues

If tests are slow:
1. Use `--parallel` (enabled by default)
2. Reduce `--runs` for faster feedback during development
3. Use `--scenario` to test specific scenarios
4. Check if procedures have unnecessary retries or delays

## Examples

See `examples/with-bdd-tests.lua` for a complete example demonstrating:
- Multiple scenarios
- Custom steps
- Evaluation configuration
- All major step types

## API Reference

See `tactus/testing/README.md` for complete API documentation.




