# Tactus

**Tactus**: A Lua-based DSL for defining and executing agentic workflows.

> **⚠️ Status: Alpha** - Tactus is in early development. Only a subset of the [specification](SPECIFICATION.md) is currently implemented. See [IMPLEMENTATION.md](IMPLEMENTATION.md) for details on what's complete and what's missing. The API is subject to change.

Tactus implements the **"Give an Agent a Tool"** programming paradigm: instead of writing explicit code to handle every edge case, you define capabilities (tools) and goals, then let an intelligent agent figure out how to use them to solve the problem.

## Quick Start

### Installation

```bash
pip install tactus
```

### Your First Procedure: Hello and Done

Here's a complete working example that demonstrates the core concepts of Tactus. We define an agent with a goal and a tool, then use Lua to orchestrate the workflow.

Create a file `hello.yaml`:

```yaml
name: hello_world
version: 1.0.0
class: LuaDSL

# Define typed parameters with defaults
params:
  name:
    type: string
    default: "World"

# 1. Define the Agent and its Tools
agents:
  greeter:
    provider: openai
    model: gpt-4o-mini
    
    # The system prompt defines the agent's goal and behavior
    system_prompt: |
      You are a friendly greeter. Greet the user by name: {params.name}
      When done, call the done tool.
    
    # Optional: kick off the conversation
    initial_message: "Please greet the user."
    
    # Tools the agent can use (procedures can also be tools)
    tools:
      - done

# 2. Define the Orchestration Logic (Lua)
procedure: |
  -- Loop until the agent decides to use the 'done' tool
  repeat
    Greeter.turn()  -- Give the agent a turn to think and act
  until Tool.called("done")

  -- Return the result captured from the tool call
  return {
    completed = true,
    greeting = Tool.last_call("done").args.reason
  }
```

Run it:

```bash
export OPENAI_API_KEY=your-key
tactus run hello.yaml
```

**What's happening here:**

1. **Parameters** (`params`): Define typed inputs with defaults. These can be overridden at runtime and are available in templates as `{params.name}`.

2. **Agents** (`agents`): Each agent has a model, system prompt, and tools. When you define an agent named `greeter`, the primitive `Greeter.turn()` becomes available in Lua.

3. **Procedure** (`procedure`): This is your workflow logic in Lua. You control the flow explicitly—loops, conditionals, error handling—while the agent handles the intelligence within each turn.

This separation of concerns is key: **you control the workflow structure, the agent handles the decision-making within that structure.**

## Key Features

### Human-in-the-Loop (HITL)

Tactus has first-class support for human oversight and collaboration. You can request approval, input, or review at any point in your workflow.

**Request approval before critical actions:**

```lua
local approved = Human.approve({
  message = "Deploy to production?",
  context = {environment = "prod", version = "2.1.0"},
  timeout = 3600,  -- seconds
  default = false
})

if approved then
  deploy_to_production()
else
  Log.info("Deployment cancelled by operator")
end
```

**Request human input:**

```lua
local topic = Human.input({
  message = "What topic should I research next?",
  placeholder = "Enter a topic...",
  timeout = nil  -- wait forever
})

if topic then
  Procedure.run("researcher", {query = topic})
end
```

**Request review of generated content:**

```lua
local review = Human.review({
  message = "Please review this generated document",
  artifact = generated_content,
  artifact_type = "document",
  options = {
    {label = "Approve", type = "action"},
    {label = "Reject", type = "cancel"},
    {label = "Revise", type = "action"}
  },
  timeout = 86400  -- 24 hours
})

if review.decision == "Approve" then
  publish(generated_content)
elseif review.decision == "Revise" then
  State.set("human_feedback", review.feedback)
  -- retry with feedback
end
```

**Declare HITL points in YAML for reusable workflows:**

```yaml
hitl:
  confirm_publish:
    type: approval
    message: "Publish this document to production?"
    timeout: 3600
    default: false
```

Then reference them in your procedure:

```lua
local approved = Human.approve("confirm_publish")
```

### Multi-Model and Multi-Provider Support

Use different models and providers for different tasks within the same workflow. **Every agent must specify a `provider:`** (either directly or via `default_provider:` at the procedure level).

**Supported providers:** `openai`, `bedrock`

**Mix models for different capabilities:**

```yaml
agents:
  researcher:
    provider: openai
    model: gpt-4o  # Use GPT-4o for complex research
    system_prompt: "Research the topic thoroughly..."
    tools: [search, done]
  
  summarizer:
    provider: openai
    model: gpt-4o-mini  # Use GPT-4o-mini for simple summarization
    system_prompt: "Summarize the findings concisely..."
    tools: [done]
```

**Mix providers (OpenAI + Bedrock):**

```yaml
agents:
  openai_analyst:
    provider: openai
    model: gpt-4o
    system_prompt: "Analyze the data..."
    tools: [done]
  
  bedrock_reviewer:
    provider: bedrock
    model: anthropic.claude-3-5-sonnet-20240620-v1:0
    system_prompt: "Review the analysis..."
    tools: [done]
```

**Configure model-specific parameters:**

```yaml
agents:
  creative_writer:
    provider: openai
    model:
      name: gpt-4o
      temperature: 0.9  # Higher creativity
      max_tokens: 2000
    system_prompt: "Write creatively..."
    tools: [done]
  
  reasoning_agent:
    provider: openai
    model:
      name: gpt-5  # Reasoning model
      openai_reasoning_effort: high
      max_tokens: 4000
    system_prompt: "Solve this complex problem..."
    tools: [done]
```

**Configuration via `.tactus/config.yml`:**

```yaml
# OpenAI credentials
openai_api_key: sk-...

# AWS Bedrock credentials
aws_access_key_id: AKIA...
aws_secret_access_key: ...
aws_default_region: us-east-1

# Optional defaults
default_provider: openai
default_model: gpt-4o
```

### Typed Parameters

Parameters are defined with JSON Schema types, providing validation and enabling rich UIs.

```yaml
params:
  topic:
    type: string
    required: true
    description: "The topic to research"
    
  depth:
    type: string
    enum: [shallow, deep]
    default: shallow
    
  max_results:
    type: number
    default: 10
    
  include_sources:
    type: boolean
    default: true
```

**Why this matters:**

- **Validation**: Parameters are validated before execution
- **Documentation**: Types and descriptions serve as inline documentation
- **UI Generation**: Different client applications can generate appropriate UIs:
  - CLI: command-line flags with type checking
  - Web UI: forms with dropdowns, number inputs, checkboxes
  - IDE: autocomplete and inline documentation
  - API: OpenAPI/JSON Schema for validation

Parameters are accessed in templates as `{params.topic}` and in Lua as `params.topic`.

### Asynchronous Execution

Tactus is built on **async I/O** from the ground up, making it ideal for LLM-based workflows where you spend most of your time waiting for API responses.

**Why async I/O matters for LLMs:**

- **Not multi-threading**: Async I/O uses a single thread with cooperative multitasking
- **Perfect for I/O-bound tasks**: While waiting for one LLM response, handle other requests
- **Efficient resource usage**: No thread overhead, minimal memory footprint
- **Natural for LLM workflows**: Most time is spent waiting for API calls, not computing

**Spawn async procedures:**

```lua
-- Start multiple research tasks in parallel
local handles = {}
for _, topic in ipairs(topics) do
  handles[topic] = Procedure.spawn("researcher", {query = topic})
end

-- Wait for all to complete
Procedure.wait_all(handles)

-- Collect results
local results = {}
for topic, handle in pairs(handles) do
  results[topic] = Procedure.result(handle)
end
```

**Check status and wait with timeout:**

```lua
local handle = Procedure.spawn("long_task", params)

-- Check status without blocking
local status = Procedure.status(handle)
if status.waiting_for_human then
  notify_channel("Task waiting for approval")
end

-- Wait with timeout
local result = Procedure.wait(handle, {timeout = 300})
if not result then
  Log.warn("Task timed out")
end
```

### Context Engineering

Tactus gives you fine-grained control over what each agent sees in the conversation history. This is crucial for multi-agent workflows where different agents need different perspectives.

**Message classification with `humanInteraction`:**

Every message has a classification that determines visibility:

- `INTERNAL`: Agent reasoning, hidden from humans
- `CHAT`: Normal human-AI conversation
- `NOTIFICATION`: Progress updates to humans
- `PENDING_APPROVAL`: Waiting for human approval
- `PENDING_INPUT`: Waiting for human input
- `PENDING_REVIEW`: Waiting for human review

**Filter conversation history per agent:**

```yaml
agents:
  worker:
    system_prompt: "Process the task..."
    tools: [search, analyze, done]
    
    # Control what this agent sees
    filter:
      class: ComposedFilter
      chain:
        - class: TokenBudget
          max_tokens: 120000
        - class: LimitToolResults
          count: 2  # Only show last 2 tool results
```

**Manage session state programmatically:**

```lua
-- Inject context for the next turn
Session.inject_system("Focus on the security implications")

-- Access conversation history
local history = Session.history()

-- Clear history for a fresh start
Session.clear()

-- Save/load conversation state
Session.save_to_node(checkpoint_node)
Session.load_from_node(checkpoint_node)
```

**Why this matters:**

- **Token efficiency**: Keep context within model limits
- **Agent specialization**: Each agent sees only what's relevant to its role
- **Privacy**: Hide sensitive information from certain agents
- **Debugging**: Control visibility for testing and development

### Procedural Workflow Control

The `procedure` section is your workflow entry point. It's written in Lua, giving you explicit control over execution flow.

**You control the structure:**

```lua
procedure: |
  -- Explicit loops
  repeat
    Worker.turn()
  until Tool.called("done") or Iterations.exceeded(20)
  
  -- Conditionals
  if State.get("needs_review") then
    local approved = Human.approve({message = "Continue?"})
    if not approved then
      return {completed = false, reason = "rejected"}
    end
  end
  
  -- Error handling
  local ok, result = pcall(function()
    return Procedure.run("risky_task", params)
  end)
  
  if not ok then
    Log.error("Task failed: " .. tostring(result))
    return {success = false, error = result}
  end
  
  -- Return structured results
  return {
    success = true,
    items_processed = State.get("count"),
    result = result
  }
```

**Checkpointing for reliability:**

Tactus automatically checkpoints agent turns and can resume from where it left off:

```lua
-- Checkpoint expensive operations
local data = Step.run("fetch_data", function()
  return expensive_api_call()
end)

-- On retry/resume, this returns the cached result
-- without re-running the expensive operation
```

**Why Lua for orchestration:**

- **Explicit control**: No hidden planning or black-box behavior
- **Familiar syntax**: Simple, readable, widely understood
- **Deterministic**: Same inputs produce same outputs (with checkpointing)
- **Debuggable**: Step through logic, inspect state, understand execution
- **Portable**: Procedures work identically in local and cloud environments

## Philosophy & Research

Tactus is built on the convergence of two critical insights: the necessity of **Self-Evolution** for future intelligence, and the requirement for **Bounded Control** in present-day production.

### 1. The Substrate for Self-Evolution

The path to Artificial Super Intelligence (ASI) lies in **Self-Evolving Agents**—systems that can adapt and improve their own components over time. A major 2025 survey, *[A Survey of Self-Evolving Agents](https://arxiv.org/abs/2507.21046)*, identifies four dimensions where evolution must occur:

*   **Models**: Optimizing prompts and fine-tuning weights.
*   **Memory**: Accumulating and refining experience.
*   **Tools**: Creating and mastering new capabilities.
*   **Architecture**: Rewriting the flow of logic and interaction.

**The "Agent as Code" Advantage**

For an agent to evolve, it must be able to modify itself. In traditional frameworks, logic is locked in compiled code or complex Python class hierarchies. Tactus takes a radical approach: **The entire agent is defined as data.**

By defining the agent's prompts, tools, and logic in a transparent, editable Lua DSL, Tactus makes the agent's own structure accessible to itself. This textual representation allows an agent to read, analyze, and *rewrite* its own definition, unlocking the potential for true self-evolution across all four dimensions.

### 2. Production Reality: Control > Autonomy

While evolution is the future, reliability is the present requirement. Research into deployed systems (*[Measuring Agents in Production](https://arxiv.org/abs/2512.04123)*) shows that successful agents rely on **constrained deployment** and **human oversight**, not open-ended "magic."

Tactus bridges this gap. It offers the **evolutionary potential** of "Agent as Code" while enforcing the **production reliability** of a strict Lua runtime. You get:

*   **Controllability**: Explicit loops and conditionals, not black-box planning.
*   **Human-in-the-Loop**: First-class primitives for approval and oversight.
*   **Bounded Autonomy**: The "Give an Agent a Tool" paradigm—defining capabilities and goals—within a controlled environment.

## Complete Feature List

- **Declarative Workflows**: Define agent workflows in pure Lua DSL
- **Multi-Provider Support**: Use OpenAI and AWS Bedrock models in the same workflow
- **Multi-Model Support**: Different agents can use different models (GPT-4o, Claude, etc.)
- **Human-in-the-Loop**: Built-in support for human approval, input, and review
- **Asynchronous Execution**: Native async I/O for efficient LLM workflows
- **Context Engineering**: Fine-grained control over conversation history per agent
- **Typed Parameters**: JSON Schema validation with UI generation support
- **Checkpointing**: Automatic workflow checkpointing and resume
- **Pluggable Backends**: Storage, HITL, and chat recording via Pydantic protocols
- **LLM Integration**: Works with OpenAI and Bedrock via [pydantic-ai](https://github.com/pydantic/pydantic-ai)
- **Standalone CLI**: Run workflows without any infrastructure
- **Type-Safe**: Pydantic models throughout for validation and type safety

**Note**: Some features from the [specification](SPECIFICATION.md) are not yet implemented, including `guards`, `dependencies`, inline procedure definitions, and advanced HITL configuration. See [IMPLEMENTATION.md](IMPLEMENTATION.md) for the complete status.

## Architecture

Tactus is built around three core abstractions:

1. **StorageBackend**: Persists procedure state and checkpoints
2. **HITLHandler**: Manages human-in-the-loop interactions
3. **ChatRecorder**: Records conversation history

These are defined as Pydantic protocols, allowing you to plug in any implementation:

```python
from tactus import TactusRuntime
from tactus.adapters.memory import MemoryStorage
from tactus.adapters.cli_hitl import CLIHITLHandler

runtime = TactusRuntime(
    procedure_id="my-workflow",
    storage_backend=MemoryStorage(),
    hitl_handler=CLIHITLHandler(),
    chat_recorder=None  # Optional
)

result = await runtime.execute(yaml_config, context)
```

## CLI Commands

```bash
# Run a workflow
tactus run workflow.tactus.lua
tactus run workflow.tactus.lua --param task="Analyze data"

# Validate a workflow
tactus validate workflow.tactus.lua
```

## Tactus IDE

Tactus includes a full-featured IDE for editing `.tactus.lua` files with instant feedback and intelligent code completion.

### Features

- **Instant syntax validation** - TypeScript parser provides immediate feedback (< 10ms)
- **Semantic intelligence** - Python LSP server for completions and hover info
- **Monaco Editor** - Same editor as VS Code
- **Hybrid validation** - Fast client-side syntax + smart backend semantics
- **Offline capable** - Basic editing works without backend
- **Cross-platform** - Built with Electron for desktop support

### Architecture: Hybrid Validation

The IDE uses a two-layer validation approach for optimal performance:

**Layer 1: TypeScript Parser (Client-Side, Instant)**
- Validates syntax as you type (< 10ms)
- Works offline, no backend needed
- Shows syntax errors immediately
- ANTLR-generated from same grammar as Python parser

**Layer 2: Python LSP (Backend, Semantic)**
- Provides intelligent completions
- Hover documentation for agents, parameters, outputs
- Cross-reference validation
- Debounced (300ms) to reduce load

This provides the best of both worlds: zero-latency syntax checking with intelligent semantic features.

### Running the IDE

```bash
# Terminal 1: Start the backend LSP server
cd tactus-ide/backend
pip install -r requirements.txt
python app.py  # Runs on port 5001

# Terminal 2: Start the IDE frontend
cd tactus-ide/frontend
npm install
npm run dev  # Runs on port 3000
```

Open http://localhost:3000 in your browser to use the IDE.

**Note**: Backend uses port 5001 (not 5000) because macOS AirPlay Receiver uses port 5000.

### Validation Layers in Action

**Layer 1: TypeScript (Instant)**
- Syntax errors (missing braces, parentheses)
- Bracket matching
- Basic structure validation
- Works offline

**Layer 2: Python LSP (Semantic)**
- Missing required fields (e.g., agent without provider)
- Cross-reference validation (e.g., undefined agent referenced)
- Context-aware completions
- Hover documentation
- Signature help

## Documentation

- [**Specification (DSL Reference)**](SPECIFICATION.md) - The official specification for the Tactus domain-specific language.
- [**Implementation Guide**](IMPLEMENTATION.md) - Maps the specification to the actual codebase implementation. Shows where each feature is implemented, what's complete, and what's missing relative to the specification.
- [**Testing Strategy**](TESTING.md) - Testing approach, frameworks, and guidelines for adding new tests.
- [**Examples**](examples/) - Run additional example procedures to see Tactus in action
- **Primitives Reference** (See `tactus/primitives/`)
- **Storage Adapters** (See `tactus/adapters/`)

## Integration

Tactus is designed to be integrated into larger systems. You can create custom adapters for your storage backend, HITL system, and chat recording.

## Development

```bash
# Clone the repository
git clone https://github.com/AnthusAI/Tactus.git
cd Tactus

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
behave --summary  # BDD integration tests
pytest tests/     # Unit tests

# Run with coverage
pytest --cov=tactus --cov-report=html

# See TESTING.md for detailed testing documentation
```

### Parser Generation

Tactus uses ANTLR4 to generate parsers from the Lua grammar for validation.

**Requirements:**
- **Docker** (required only for regenerating parsers)
- Generated parsers are committed to repo

**When to regenerate:**
- Only when modifying grammar files in `tactus/validation/grammar/`
- Not needed for normal development

**How to regenerate:**
```bash
# Ensure Docker is running
make generate-parsers

# Or individually:
make generate-python-parser
make generate-typescript-parser
```

See `tactus/validation/README.md` for detailed documentation.

## License

MIT License - see LICENSE file for details.
