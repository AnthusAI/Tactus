# Tactus Examples

This directory contains example Tactus procedure files that demonstrate how to use the Tactus Lua DSL.

Examples are organized by category with numbered prefixes for easy navigation:
- **01-09**: Basic examples (hello world, parameters, simple agents)
- **10-19**: Feature demonstrations (state, message history, structured output)
- **20-29**: BDD testing examples
- **30-39**: Evaluation examples
- **40-49**: Durability features (models, sub-procedures, checkpoints)
- **90-99**: Miscellaneous utilities

## Running Examples

Each example can be run directly with the Tactus CLI:

```bash
tactus run examples/01-basics-hello-world.tac
tactus run examples/03-basics-parameters.tac --param task="My task" --param count=10
```

## Example Files

### Basics (01-09)

#### 01-basics-hello-world.tac

A basic "Hello World" example that demonstrates:
- Simple workflow execution
- State management with State primitive
- Logging operations
- Output schema validation

**Run:**
```bash
tactus run examples/01-basics-hello-world.tac
```

#### 02-basics-simple-logic.tac

Demonstrates pure Lua logic without agents:
- Conditional logic and loops
- State operations
- Structured outputs

**Run:**
```bash
tactus run examples/02-basics-simple-logic.tac
```

#### 03-basics-parameters.tac

Shows how to use parameters:
- Declaring parameters with types and defaults
- Accessing parameters in workflow code
- Overriding parameters via CLI

**Run:**
```bash
# Use defaults
tactus run examples/03-basics-parameters.tac

# Override parameters
tactus run examples/03-basics-parameters.tac --param task="Custom task" --param count=5
```

#### 04-basics-simple-agent.tac

Demonstrates agent interaction:
- Defining agents with system prompts
- Agent turns and tool calls
- LLM integration with OpenAI
- Structured output from agent responses

**Run:**
```bash
tactus run examples/04-basics-simple-agent.tac
```

#### 05-basics-multi-model.tac

Shows multi-model configuration:
- Using different models for different agents
- Model-specific parameters (temperature, max_tokens)
- Default provider and model settings

**Run:**
```bash
tactus run examples/05-basics-multi-model.tac
```

### Features (10-19)

#### 10-feature-state.tac

Demonstrates state operations:
- Setting and getting state values
- Incrementing numeric state
- Iterating with state tracking
- Returning structured output

**Run:**
```bash
tactus run examples/10-feature-state.tac
```

#### 11-feature-message-history.tac

Shows message history management:
- Isolated vs shared message history
- Message history filters
- Agent-level overrides

**Run:**
```bash
tactus run examples/11-feature-message-history.tac
```

#### 12-feature-structured-output.tac

Demonstrates structured output validation:
- Defining output schemas
- Type-safe agent responses
- Automatic validation and retry

**Run:**
```bash
tactus run examples/12-feature-structured-output.tac
```

#### 13-feature-session.tac

Shows session management:
- Session operations
- Message injection
- History manipulation

**Run:**
```bash
tactus run examples/13-feature-session.tac
```

### BDD Testing (20-29)

#### 20-bdd-complete.tac

Complete BDD testing example:
- Embedded Gherkin specifications
- Built-in step definitions
- Custom step definitions
- Multiple scenarios

**Run:**
```bash
tactus test examples/20-bdd-complete.tac --mock
```

#### 21-bdd-passing.tac

Example with passing BDD tests:
- Well-defined scenarios
- Comprehensive assertions
- Self-validating behavior

**Run:**
```bash
tactus test examples/21-bdd-passing.tac --mock
```

#### 22-bdd-fuzzy-matching.tac

Fuzzy matching for scalar outputs:
- Thresholded fuzzy matches for output strings
- Using mocks inside the specification scenarios

**Run:**
```bash
tactus test examples/22-bdd-fuzzy-matching.tac --mock
```

### Evaluations (30-39)

#### 30-eval-simple.tac

Simple evaluation example:
- Basic evaluator setup
- Success rate measurement

**Run:**
```bash
tactus eval examples/30-eval-simple.tac --runs 10
```

#### 31-eval-demo.tac

Evaluation demonstration:
- Multiple evaluators
- Different evaluation types

**Run:**
```bash
tactus eval examples/31-eval-demo.tac --runs 10
```

#### 32-eval-success-rate.tac

Success rate evaluation:
- Pass/fail criteria
- Statistical analysis

**Run:**
```bash
tactus eval examples/32-eval-success-rate.tac --runs 20
```

#### 33-eval-thresholds.tac

Threshold-based evaluation:
- Quality gates
- CI/CD integration

**Run:**
```bash
tactus eval examples/33-eval-thresholds.tac --runs 10
```

#### 34-eval-dataset.tac

External dataset evaluation:
- Loading data from JSONL files
- Dataset-based testing

**Run:**
```bash
tactus eval examples/34-eval-dataset.tac --runs 10
```

#### 35-eval-trace.tac

Trace inspection evaluation:
- Analyzing execution traces
- Tool call validation

**Run:**
```bash
tactus eval examples/35-eval-trace.tac --runs 10
```

#### 36-eval-advanced.tac

Advanced evaluators:
- Regex matching
- JSON schema validation
- Range checks

**Run:**
```bash
tactus eval examples/36-eval-advanced.tac --runs 10
```

#### 37-eval-comprehensive.tac

Comprehensive evaluation suite:
- All evaluator types
- Complete testing workflow

**Run:**
```bash
tactus eval examples/37-eval-comprehensive.tac --runs 10
```

### Durability Features (40-49)

#### 39-model-simple.tac

Simple model primitive example:
- HTTP-based model inference
- Model prediction with auto-checkpointing
- Using httpbin.org for testing

**Run:**
```bash
tactus run examples/39-model-simple.tac --param text="Hello world"
```

#### 40-model-text-classifier.tac

Text classification with routing:
- Sentiment analysis model
- Agent routing based on model output
- HTTP model backend

**Run:**
```bash
tactus run examples/40-model-text-classifier.tac --param text="I love this product!"
```

#### 41-model-pytorch.tac

PyTorch model integration:
- Loading .pt model files
- PyTorch inference with auto-checkpointing
- Agent response based on model prediction

**Requirements:**
```bash
pip install torch
cd examples/models
python create_sentiment_model.py
```

**Run:**
```bash
tactus run examples/41-model-pytorch.tac --param customer_message="This is great!"
```

#### 43-sub-procedure-simple.tac

Simple sub-procedure composition:
- Calling helper procedures
- Auto-checkpointing of sub-procedure calls
- Result aggregation

**Run:**
```bash
tactus run examples/43-sub-procedure-simple.tac --param numbers="[2,3,4]"
```

#### 44-sub-procedure-composition.tac

Complex sub-procedure composition:
- Multi-step data processing pipeline
- Multiple sub-procedure calls
- Agent integration with sub-procedures
- Durable workflow composition

**Run:**
```bash
tactus run examples/44-sub-procedure-composition.tac --param numbers="[5,10,15]"
```

#### 45-sub-procedure-recursive.tac

Recursive sub-procedure calls:
- Factorial calculation via recursion
- Auto-checkpointing of recursive calls
- Recursion depth tracking

**Run:**
```bash
tactus run examples/45-sub-procedure-recursive.tac --param n=5
```

#### 46-checkpoint-explicit.tac

Explicit checkpoint primitive:
- Manual state checkpointing with checkpoint()
- Granular control over durability
- Checkpoint counter tracking

**Run:**
```bash
tactus run examples/46-checkpoint-explicit.tac --param numbers="[2,4,6]"
```

#### 47-checkpoint-expensive-ops.tac

Checkpointing expensive operations:
- Cache results of expensive computations
- Skip expensive work on replay
- Performance optimization through checkpointing

**Run:**
```bash
tactus run examples/47-checkpoint-expensive-ops.tac --param iterations=1000
```

#### 48-script-mode-simple.tac

Script mode with top-level input/output:
- No explicit procedure() definition needed
- Top-level input and output declarations
- Simplified syntax for simple workflows

**Run:**
```bash
tactus run examples/48-script-mode-simple.tac --param name="Alice"
```

### Miscellaneous (90-99)

#### 99-misc-test-loading.tac

Test loading indicators and UI behavior:
- Loading state management
- Progress indication

**Run:**
```bash
tactus run examples/99-misc-test-loading.tac
```

## Configuration

Some examples require configuration, particularly LLM-based examples that need an OpenAI API key.

### Setting Up Configuration

1. Copy the example config file:
   ```bash
   cp .tactus/config.yml.example .tactus/config.yml
   ```

2. Edit `.tactus/config.yml` and add your OpenAI API key:
   ```yaml
   openai_api_key: "sk-your-actual-api-key-here"
   ```

The `.tactus/config.yml` file is already in `.gitignore` so your API key won't be committed.

The configuration is automatically loaded when you run `tactus` commands. The `openai_api_key` value will be set as the `OPENAI_API_KEY` environment variable.

### Examples Requiring Configuration

- `04-basics-simple-agent.tac` - Requires `OPENAI_API_KEY` to call the LLM
- `05-basics-multi-model.tac` - Requires `OPENAI_API_KEY` to call the LLM

Examples that don't require external services (like `01-basics-hello-world.tac`) work without any configuration.

## File Extension

Example files use the `.tac` extension to indicate they are Tactus procedure files written in pure Lua DSL.

## Self-Validating Files

One of Tactus's key features is that procedure files can be **self-validating** through embedded BDD specifications. Files that include `specifications([[...]])` blocks contain their own test cases and can verify their correctness automatically.

### Testing Self-Validating Files

Run tests for any file with embedded specifications:

```bash
# Test a single file
tactus test examples/01-basics-hello-world.tac --mock

# Test all files in the directory
for file in examples/*.tac; do tactus test "$file" --mock; done
```

The `--mock` flag runs tests without requiring external services (like LLM API calls), making tests fast and deterministic.

### Benefits of Self-Validating Files

- ✅ **Trust**: Files with passing tests are known to work correctly
- ✅ **Documentation**: Tests serve as executable examples of expected behavior
- ✅ **Regression Prevention**: Changes that break functionality are caught immediately
- ✅ **No External Dependencies**: Mock mode tests run without API keys or network calls

### Which Files Are Self-Validating?

You can identify self-validating files by checking for test results:

```bash
# Files with specifications will show test results
tactus test examples/01-basics-hello-world.tac --mock
# Output: "1 scenarios (1 passed, 0 failed)"

# Files without specifications will show a warning
tactus test examples/some-file.tac --mock
# Output: "⚠ Warning: No specifications defined"
```

All current example files include BDD specifications and are self-validating.

## Validation

You can also validate files without running tests:

```bash
tactus validate examples/01-basics-hello-world.tac
```

This uses the ANTLR-generated parser to check syntax and DSL structure, but doesn't verify runtime behavior like tests do.
