# Gherkin BDD Testing Implementation Summary

## What Was Implemented

A complete first-class BDD testing framework for Tactus using Gherkin syntax, integrated directly into the DSL with parser warnings, parallel execution, and consistency evaluation.

## Key Components

### 1. Grammar & Validation Updates

**Files Modified:**
- `tactus/validation/semantic_visitor.py` - Added recognition for `specifications()`, `step()`, `evaluation()`
- `tactus/core/registry.py` - Added fields for Gherkin specs, custom steps, evaluation config
- `tactus/cli/app.py` - Updated to recognize `.lua` extension

**Features:**
- Parser recognizes `specifications([[...]])` construct
- Parser recognizes `step("text", function)` construct
- Parser recognizes `evaluation({...})` construct
- Validator warns if no specifications defined

### 2. Gherkin Parser Integration

**Files Created:**
- `tactus/testing/gherkin_parser.py` - Parse Gherkin using `gherkin-official` library
- `tactus/testing/models.py` - Pydantic models for all results

**Features:**
- Parse Gherkin text to structured AST
- Convert to Pydantic models (ParsedFeature, ParsedScenario, ParsedStep)
- Full support for tags, descriptions, multiple scenarios
- Error handling for invalid Gherkin syntax

### 3. Built-in Step Library

**Files Created:**
- `tactus/testing/steps/registry.py` - Step pattern matching with regex
- `tactus/testing/steps/builtin.py` - Comprehensive built-in steps
- `tactus/testing/steps/custom.py` - Custom Lua step manager

**Built-in Steps Implemented:**
- **Tool steps**: `the {tool} tool should be called`, `at least {n} times`, `with {param}={value}`
- **Stage steps**: `the stage should be {stage}`, `transition from {s1} to {s2}`
- **State steps**: `the state {key} should be {value}`, `should exist`
- **Completion steps**: `should complete successfully`, `stop reason should contain {text}`
- **Iteration steps**: `iterations should be less than {n}`, `between {min} and {max}`
- **Parameter steps**: `the {param} parameter is {value}`
- **Agent steps**: `the {agent} agent takes turns`, `the procedure runs`

### 4. Behave Integration Layer

**Files Created:**
- `tactus/testing/context.py` - Test context for step execution
- `tactus/testing/behave_integration.py` - Generate .feature files and step definitions

**Features:**
- Generate Behave-compatible .feature files from parsed Gherkin
- Generate step_definitions.py that bridges to Tactus steps
- Generate environment.py for Behave context setup
- Automatic scenario tagging for filtering

### 5. Test Runner

**Files Created:**
- `tactus/testing/test_runner.py` - Parallel test execution

**Features:**
- Run all scenarios once (single-run mode)
- Parallel execution using multiprocessing
- Scenario filtering by name
- Sequential fallback option
- Structured Pydantic results (no text parsing)
- Automatic cleanup of temp files

### 6. Evaluation Runner

**Files Created:**
- `tactus/testing/evaluation_runner.py` - Multi-run consistency evaluation

**Features:**
- Run each scenario N times
- Parallel execution of iterations
- Calculate success rate (% passed)
- Calculate timing statistics (mean, median, stddev)
- Calculate consistency score (identical behavior across runs)
- Detect flakiness (some pass, some fail)
- Per-scenario detailed metrics

### 7. CLI Commands

**Commands Added:**
- `tactus test <file>` - Run scenarios once
- `tactus evaluate <file>` - Run scenarios N times

**Options:**
- `--scenario` - Run specific scenario
- `--runs` - Number of runs per scenario (evaluate only)
- `--parallel` / `--no-parallel` - Control parallel execution
- `--workers` - Number of parallel workers (evaluate only)
- `--verbose` - Detailed output

### 8. IDE Integration

**Files Created:**
- `tactus/testing/events.py` - Structured log events

**Events:**
- TestStartedEvent, TestCompletedEvent
- TestScenarioStartedEvent, TestScenarioCompletedEvent
- EvaluationStartedEvent, EvaluationCompletedEvent
- EvaluationScenarioStartedEvent, EvaluationScenarioCompletedEvent
- EvaluationProgressEvent

All events are Pydantic models that can be serialized to JSON for IDE display.

### 9. Documentation

**Files Created:**
- `tactus/testing/README.md` - Framework documentation
- `docs/BDD_TESTING.md` - Complete user guide
- `examples/with-bdd-tests.lua` - Example procedure with specs

**Files Updated:**
- `README.md` - Added BDD testing section
- `SPECIFICATION.md` - Added Gherkin BDD Testing section
- `IMPLEMENTATION.md` - Documented BDD testing implementation

### 10. Tests

**Files Created:**
- `tests/testing/test_gherkin_parser.py` - Gherkin parser tests (5 tests)
- `tests/testing/test_step_registry.py` - Step registry tests (9 tests)
- `tests/testing/test_models.py` - Pydantic model tests (7 tests)
- `tests/testing/test_integration.py` - Integration tests (3 tests)

**Test Results:**
- 24 tests total
- All passing
- Coverage of core functionality

## Dependencies Added

```toml
dependencies = [
  # ... existing ...
  "behave>=1.2.6",
  "gherkin-official>=28.0.0",
]
```

## File Structure

```
tactus/
├── testing/
│   ├── __init__.py
│   ├── gherkin_parser.py       # Parse Gherkin text
│   ├── models.py                # Pydantic result models
│   ├── context.py               # Test context for steps
│   ├── behave_integration.py   # Generate .feature files
│   ├── test_runner.py           # Single-run test execution
│   ├── evaluation_runner.py    # Multi-run evaluation
│   ├── events.py                # Structured log events
│   ├── README.md                # Framework documentation
│   └── steps/
│       ├── __init__.py
│       ├── registry.py          # Step pattern matching
│       ├── builtin.py           # Built-in step library
│       └── custom.py            # Custom Lua steps
├── cli/
│   └── app.py                   # Added test/evaluate commands
├── validation/
│   └── semantic_visitor.py      # Added specs validation
└── core/
    └── registry.py              # Added specs fields

tests/
└── testing/
    ├── __init__.py
    ├── test_gherkin_parser.py
    ├── test_step_registry.py
    ├── test_models.py
    └── test_integration.py

docs/
└── BDD_TESTING.md               # Complete user guide

examples/
└── with-bdd-tests.lua           # Example procedure
```

## Usage Example

```lua
-- procedure.lua
name("my_procedure")
version("1.0.0")

agent("worker", {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "Do the work",
  tools = {"search", "done"}
})

procedure(function()
  Stage.set("working")
  repeat
    Worker.turn()
  until Tool.called("done")
  Stage.set("complete")
end)

specifications([[
Feature: My Procedure

  Scenario: Worker completes task
    Given the procedure has started
    When the worker agent takes turns
    Then the search tool should be called
    And the done tool should be called
    And the stage should transition from working to complete
    And the procedure should complete successfully
]])

step("custom validation", function()
  assert(State.get("count") > 0, "Count should be positive")
end)

evaluation({
  runs = 10,
  parallel = true
})
```

```bash
# Validate
$ tactus validate procedure.lua
✓ DSL is valid

# Run tests
$ tactus test procedure.lua
Feature: My Procedure
  ✓ Scenario: Worker completes task (1.2s)

1 scenarios (1 passed)

# Evaluate consistency
$ tactus evaluate procedure.lua --runs 10
Scenario: Worker completes task
  Success Rate: 90% (9/10)
  Duration: 1.23s (±0.15s)
  Consistency: 90%
  ⚠️  FLAKY - Inconsistent results detected
```

## Design Decisions

### Why Behave?

- **Pure Gherkin syntax** - No pytest wrappers or decorators
- **Programmatic API** - Direct access to Feature/Scenario/Step objects
- **Rich object model** - No text parsing needed
- **Mature and stable** - Well-tested BDD framework

### Why Custom Multiprocessing?

- **Full control** - Can run same scenario N times in parallel
- **Simpler** - No dependency on BehaveX or other wrappers
- **Better metrics** - Direct access to results for consistency calculation
- **Lightweight** - Minimal code, easy to maintain

### Why Built-in Steps?

- **Tactus-specific** - Steps designed for Tactus primitives
- **No boilerplate** - Users don't write step definitions
- **Natural language** - Tests read like specifications
- **Extensible** - Custom steps for advanced cases

## What's Next

Potential future enhancements:

1. **Background sections** - Shared setup across scenarios
2. **Scenario Outlines** - Parameterized scenarios with Examples tables
3. **Hooks** - Before/after scenario hooks in Lua
4. **Data tables** - Support for Gherkin data tables in steps
5. **More built-in steps** - Expand the step library based on usage
6. **Coverage metrics** - Track which parts of procedure are tested
7. **Regression detection** - Compare evaluation results over time
8. **Visual reports** - HTML reports with charts and graphs

## Performance Characteristics

### Test Mode (tactus test)

- **10 scenarios, sequential**: ~10 × avg_duration
- **10 scenarios, parallel (10 workers)**: ~avg_duration
- **Speedup**: ~10x with parallel execution

### Evaluation Mode (tactus evaluate)

- **1 scenario, 10 runs, sequential**: ~10 × avg_duration
- **1 scenario, 10 runs, parallel (10 workers)**: ~avg_duration
- **5 scenarios, 10 runs each, parallel**: ~5 × avg_duration (scenarios run sequentially, runs within scenario parallel)

**Real-world example:**
- 5 scenarios, 20 runs each, 3s avg duration per run
- Sequential: 5 × 20 × 3s = 300s (5 minutes)
- Parallel: 5 × 3s = 15s (20x speedup)

## Success Criteria

All success criteria from the plan have been met:

1. ✅ Can write Gherkin specs in procedure files
2. ✅ Parser warns if specifications missing
3. ✅ Built-in steps work for all Tactus primitives
4. ✅ Custom Lua steps can be defined
5. ✅ `tactus test` runs scenarios in parallel
6. ✅ `tactus evaluate` measures consistency/reliability
7. ✅ All results are structured Pydantic models
8. ✅ IDE integration via structured log events
9. ✅ No text parsing required anywhere
10. ✅ Comprehensive tests (24 tests, all passing)


