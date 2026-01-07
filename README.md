# Tactus

**A programming language for AI agents that never lose their place.**

Tactus is a programming language with durable execution built in. Write normal imperative code—loops, conditionals, function calls—and the runtime transparently checkpoints every operation. When execution suspends for human approval, crashes, or times out, it resumes exactly where it left off.

## The Problem: Agents Need to Wait

Real-world agents can't run to completion in one shot. They need to:

- **Wait for humans**: Approval gates, reviews, input requests
- **Survive failures**: Network timeouts, API errors, process crashes
- **Run for days**: Complex tasks that span hours or weeks
- **Coordinate**: Wait for other agents, external systems, scheduled events

Traditional agent frameworks don't solve this. They give you tools for building agents, but the durability problem—persisting state, resuming execution, replaying completed work—is left to you.

## The Solution: Transparent Checkpointing

With Tactus, durability is built into the language:

```lua
-- This looks like it runs straight through
repeat
  Agent("researcher").turn()
until Tool.called("done")

-- But here execution might suspend for days
local approved = Human.approve({message = "Deploy to production?"})

-- When the human responds, execution resumes exactly here
if approved then
  deploy()
end
```

Every agent turn, every tool call, every human interaction is automatically checkpointed. No state machines. No manual serialization. No replay logic.

### Compare: Graph-Based vs. Imperative Durability

LangGraph does support persistence—when you compile a graph with a checkpointer, it saves state at every "super-step" (node boundary). But you're still designing a state machine:

```python
# LangGraph: Define state, nodes, and edges explicitly
class State(TypedDict):
    messages: list
    research_complete: bool
    approved: bool | None

graph = StateGraph(State)
graph.add_node("research", research_node)
graph.add_node("wait_approval", wait_approval_node)
graph.add_node("deploy", deploy_node)
graph.add_edge("research", "wait_approval")
graph.add_conditional_edges("wait_approval", route_on_approval, {
    "approved": "deploy",
    "rejected": END
})

# Add checkpointer for persistence
memory = SqliteSaver.from_conn_string(":memory:")
app = graph.compile(checkpointer=memory)
```

This is powerful, but your workflow must be expressed as a graph. Nodes, edges, conditional routing. The structure is explicit.

**With Tactus**, you write imperative code. Loops, conditionals, function calls—the control flow you already know:

```lua
repeat Agent("researcher").turn() until Tool.called("done")
local approved = Human.approve({message = "Deploy?"})
if approved then deploy() end
```

Same workflow. No graph definition. The runtime checkpoints every operation transparently—agent turns, tool calls, human interactions—and resumes exactly where execution left off.

The difference isn't whether checkpointing exists, but how you express your workflow. Graphs vs. imperative code. Explicit structure vs. transparent durability.

---

## Everything as Code

Tactus isn't just durable—it's designed for agents that build and modify other agents.

Most frameworks scatter agent logic across Python classes, decorators, YAML files, and configuration objects. This is opaque to AI. An agent can't easily read, understand, and improve its own definition when it's spread across a codebase.

Tactus takes a different approach: **the entire agent definition is a single, readable file.**

```lua
Agent "researcher" {
  model = "gpt-4o",
  system_prompt = "Research the topic thoroughly.",
  toolsets = {"search", "analyze", "done"}
}

Procedure "main" {
  input = {
    topic = field.string{required = true}
  },
  output = {
    findings = field.string{required = true}
  },
  function(input)
    repeat
      Agent("researcher").turn()
    until Tool.called("done")
    return {findings = Tool.last_result("done")}
  end
}

Specifications([[
Feature: Research
  Scenario: Completes research
    When the researcher agent takes turns
    Then the search tool should be called at least once
]])
```

Agents, orchestration, contracts, and tests—all in one file. All in a minimal syntax that fits in context windows and produces clean diffs.

This enables:

- **Self-evolution**: An agent reads its own definition, identifies improvements, rewrites itself
- **Agent-building agents**: A meta-agent that designs and iterates on specialized agents
- **Transparent iteration**: When an agent modifies code, you can diff the changes

---

## Safe Embedding

Tactus is designed for platforms that run user-contributed agent definitions—like n8n or Zapier, but where the automations are intelligent agents.

This requires true sandboxing. User A's agent can't escape to affect user B. Can't access the filesystem. Can't make network calls. Unless you explicitly provide tools that grant these capabilities.

Python can't be safely sandboxed. Lua was designed for it—decades of proven use in game modding, nginx plugins, Redis scripts.

Tactus agents run in a restricted Lua VM:

- No filesystem access by default
- No network access by default
- No environment variable access by default
- The tools you provide are the *only* capabilities the agent has

This makes Tactus safe for:

- Multi-tenant platforms running user-contributed agents
- Embedding in applications where untrusted code is a concern
- Letting AI agents write and execute their own orchestration logic

---

## Omnichannel Human-in-the-Loop

When an agent needs human input, *how* that request reaches the human depends on the channel. The agent shouldn't care.

Tactus separates the *what* from the *how*:

```lua
local approved = Human.approve({
  message = "Deploy to production?",
  context = {version = "2.1.0", environment = "prod"}
})
```

The agent declares what it needs. The platform decides how to render it:

| Channel | Rendering |
|---------|-----------|
| **Web** | Modal with Approve/Reject buttons |
| **Slack** | Interactive message with button actions |
| **SMS** | "Deploy v2.1.0 to prod? Reply YES or NO" |
| **Voice** | "Should I deploy version 2.1.0 to production?" |
| **Email** | Message with approve/reject links |

Because procedures declare typed inputs, platforms can auto-generate UI for any channel:

```lua
main = procedure("main", {
  input = {
    topic = { type = "string", required = true },
    depth = { type = "string", enum = {"shallow", "deep"}, default = "shallow" },
    max_results = { type = "number", default = 10 },
    include_sources = { type = "boolean", default = true },
    tags = { type = "array", default = {} },
    config = { type = "object", default = {} }
  }
}, function()
  -- Access inputs directly in Lua
  log("Researching: " .. input.topic)
  log("Depth: " .. input.depth)
  log("Max results: " .. input.max_results)

  -- Arrays and objects work seamlessly
  for i, tag in ipairs(input.tags) do
    log("Tag " .. i .. ": " .. tag)
  end

  -- ... rest of procedure
end)
```

**Input Types Supported:**
- `string`: Text values with optional enums for constrained choices
- `number`: Integers and floats
- `boolean`: True/false values
- `array`: Lists of values (converted to 1-indexed Lua tables)
- `object`: Key-value dictionaries (converted to Lua tables)

**Input Sources:**
- **CLI**: Parameters via `--param`, interactive prompting, or automatic prompting for missing required inputs
- **GUI**: Modal dialog before execution with type-appropriate form controls
- **SDK**: Direct passing via `context` parameter to `runtime.execute()`

A web app renders a form. Slack renders a modal. SMS runs a structured conversation. The CLI provides interactive prompts.

One agent definition. Every channel. Type-safe inputs everywhere.

---

## Testing Built In

When agents modify agents, verification is essential. Tactus makes BDD specifications part of the language:

```lua
specifications([[
Feature: Research Task
  Scenario: Agent completes research
    Given the procedure has started
    When the researcher agent takes turns
    Then the search tool should be called at least once
    And the done tool should be called exactly once
]])
```

Run tests with `tactus test`. Measure consistency with `tactus test --runs 10`. When an agent rewrites itself, the tests verify it still works.

---

## The Broader Context

Tactus serves a paradigm shift in programming: from anticipating every scenario to providing capabilities and goals.

Traditional code requires you to handle every case—every header name, every format, every edge condition. Miss one and your program breaks.

Agent programming inverts this: give an agent tools, describe the goal, let intelligence handle the rest.

```lua
Agent "importer" {
  system_prompt = "Extract contacts from the data. File each one you find.",
  toolsets = {"file_contact", "done"}
}
```

When a new format appears—unexpected headers, mixed delimiters, a language you didn't anticipate—the agent adapts. No code changes.

See [Give an Agent a Tool](https://github.com/AnthusAI/Give-an-Agent-a-Tool) for a deep dive on this paradigm shift.

---

## What This Enables

**Agent platforms**: Build your own n8n/Zapier where users define intelligent agents. Tactus handles sandboxing, durability, and multi-tenancy.

**Self-evolving agents**: Agents that read their own definitions, identify improvements, and rewrite themselves.

**Agents building agents**: A meta-agent that designs, tests, and iterates on specialized agents for specific tasks.

**Omnichannel deployment**: Write agent logic once. Deploy across web, mobile, Slack, SMS, voice, email.

**Long-running workflows**: Agents that wait for humans, coordinate with external systems, and run for days without losing progress.

---

## Tools

Tools are the capabilities you give to agents. Tactus supports multiple ways to define and connect tools.

### MCP Server Integration

Connect to [Model Context Protocol](https://modelcontextprotocol.io/) servers to access external tool ecosystems:

```yaml
# .tactus/config.yml
mcp_servers:
  plexus:
    command: "python"
    args: ["-m", "plexus.mcp"]
    env:
      PLEXUS_API_KEY: "${PLEXUS_API_KEY}"

  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
```

Tools from MCP servers are automatically namespaced:

```lua
Agent "worker" {
  tools = {
    "plexus_score_info",       -- From plexus server
    "filesystem_read_file",    -- From filesystem server
    "done"
  }
})
```

### Inline Lua Tools

Define tools directly in your `.tac` file—no external servers required:

**Individual tools:**

```lua
Tool "calculate_tip" {
  description = "Calculate tip amount for a bill",
  input = {
    amount = field.number{required = true},
    percent = field.number{required = true}
  },
  function(args)
    return string.format("$%.2f", args.amount * args.percent / 100)
  end
}

Agent "assistant" {
  toolsets = {"calculate_tip", "done"}
}
```

**Grouped toolsets:**

```lua
Toolset "math_tools" {
  type = "lua",
  tools = {
    {name = "add", input = {...}, handler = function(args) ... end},
    {name = "multiply", input = {...}, handler = function(args) ... end}
  }
}

Agent "calculator" {
  toolsets = {"math_tools", "done"}
}
```

**Inline agent tools:**

```lua
Agent "text_processor" {
  tools = {
    {name = "uppercase", input = {...}, handler = function(args)
      return string.upper(args.text)
    end}
  },
  toolsets = {"done"}
}
```

### Direct Tool Invocation

Call tools directly from Lua code for deterministic control:

```lua
-- Tool() returns a callable - assign it for direct use
local calculate_tip = Tool "calculate_tip" {
  description = "Calculate tip",
  input = {
    amount = field.number{required = true},
    percent = field.number{required = true}
  },
  function(args)
    return args.amount * args.percent / 100
  end
}

-- Call directly - no LLM involvement
local tip = calculate_tip({amount = 50, percent = 20})

-- Pass results to agent via context
Agent("summarizer").turn({
  context = {
    tip_calculation = tip,
    original_amount = "$50.00"
  }
})
```

### Tool Tracking

Check which tools were called and access their results:

```lua
if Tool.called("search") then
  local result = Tool.last_result("search")
  local call = Tool.last_call("search")  -- {args = {...}, result = "..."}
end
```

### Per-Turn Tool Control

Control which tools are available on each turn—essential for patterns like tool result summarization:

```lua
repeat
  Researcher.turn()  -- Has all tools

  if Tool.called("search") then
    -- Summarize with NO tools (prevents recursive calls)
    Researcher.turn({
      inject = "Summarize the search results",
      tools = {}
    })
  end
until Tool.called("done")
```

See [docs/TOOLS.md](docs/TOOLS.md) for the complete tools reference.

---

## Quick Start

### Installation

```bash
pip install tactus
```

### Your First Procedure

Create `hello.tac`:

```lua
Agent "greeter" {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = [[
    You are a friendly greeter. Greet the user by name: {input.name}
    When done, call the done tool.
  ]],
  tools = {"done"}
})

main = procedure("main", {
  input = {
    name = { type = "string", default = "World" }
  },
  output = {
    greeting = { type = "string", required = true }
  }
}, function()
  repeat
    Agent("greeter").turn()
  until Tool.called("done")

  return { greeting = Tool.last_result("done") }
end)

specifications([[
Feature: Greeting
  Scenario: Agent greets and completes
    When the greeter agent takes turns
    Then the done tool should be called exactly once
    And the procedure should complete successfully
]])
```

**Run it:**

```bash
export OPENAI_API_KEY=your-key
tactus run hello.tac
```

**Test it:**

```bash
tactus test hello.tac
```

**Evaluate consistency:**

```bash
tactus test hello.tac --runs 10
```

---

## Documentation

- **[SPECIFICATION.md](SPECIFICATION.md)** — Complete DSL reference
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)** — Implementation status and architecture
- **[docs/TOOLS.md](docs/TOOLS.md)** — Tools and MCP integration guide
- **[docs/FILE_IO.md](docs/FILE_IO.md)** — File I/O operations guide (CSV, TSV, Parquet, HDF5, Excel)
- **[examples/](examples/)** — Example procedures

---

## Key Features

### Per-Turn Tool Control

Tactus gives you fine-grained control over what tools an agent has access to on each individual turn. This enables powerful patterns like **tool result summarization**, where you want the agent to explain what a tool returned without having access to call more tools.

**The Pattern:**

```lua
Agent "researcher" {
  provider = "openai",
  model = "gpt-4o",
  system_prompt = "You are a research assistant.",
  tools = {"search", "analyze", "done"}
})

main = procedure("main", {}, function()
  repeat
    -- Main turn: agent has all tools
    Agent("researcher").turn()

    -- After each tool call, ask agent to summarize with NO tools
    if Tool.called("search") or Tool.called("analyze") then
      Agent("researcher").turn({
        inject = "Summarize the tool results above in 2-3 sentences",
        tools = {}  -- No tools for this turn!
      })
    end

  until Tool.called("done")
end)
```

This creates a rhythm: **tool call → summarization → tool call → summarization → done**

**Why this matters:**

Without per-turn control, an agent might call another tool when you just want it to explain the previous result. By temporarily restricting tools to an empty set (`tools = {}`), you ensure the agent focuses on summarization.

**Other per-turn overrides:**

```lua
-- Override model parameters for one turn
Researcher.turn({
  inject = "Be creative with this summary",
  temperature = 0.9,
  max_tokens = 500
})

-- Restrict to specific tools only
Researcher.turn({
  tools = {"search", "done"}  -- No analyze for this turn
})
```

See `examples/14-feature-per-turn-tools.tac` for a complete working example.

### File I/O Operations

Tactus provides safe file I/O operations for reading and writing data files, with all operations restricted to the current working directory for security.

**Supported Formats:**
- **CSV/TSV** — Tabular data with automatic header handling
- **JSON** — Structured data using File.read/write with Json.encode/decode
- **Parquet** — Columnar storage for analytics (via pyarrow)
- **HDF5** — Scientific data with multiple datasets (via h5py)
- **Excel** — Spreadsheets with sheet support (via openpyxl)
- **Raw text** — Plain text files and configurations

**Example:**
```lua
-- Read CSV data
local data = Csv.read("sales.csv")

-- Process data (0-indexed access)
for i = 0, data:len() - 1 do
    local row = data[i]
    -- process row...
end

-- Write results
Csv.write("results.csv", processed_data)
```

See [`docs/FILE_IO.md`](docs/FILE_IO.md) for the complete API reference and [`examples/52-file-io-basics.tac`](examples/52-file-io-basics.tac) through [`examples/58-text-file-io.tac`](examples/58-text-file-io.tac) for working examples.

### Testing & Evaluation: Two Different Concerns

Tactus provides two complementary approaches for ensuring quality, each targeting a different aspect of your agentic workflow:

#### Behavior Specifications (BDD): Testing Workflow Logic

**What it tests:** The deterministic control flow of your procedure—the Lua code that orchestrates agents, handles conditionals, manages state, and coordinates tools.

**When to use:**
- Complex procedures with branching logic, loops, and state management
- Multi-agent coordination patterns
- Error handling and edge cases
- Procedures where the *orchestration* is more complex than the *intelligence*

**How it works:**
```lua
specifications([[
Feature: Multi-Agent Research Workflow

  Scenario: Researcher delegates to summarizer
    Given the procedure has started
    When the researcher agent takes 3 turns
    Then the search tool should be called at least once
    And the researcher should call the delegate tool
    And the summarizer agent should take at least 1 turn
    And the done tool should be called exactly once
]])
```

**Key characteristics:**
- Uses Gherkin syntax (Given/When/Then)
- Runs with `tactus test`
- Can use mocks to isolate logic from LLM behavior
- Deterministic: same input → same execution path
- Fast: tests orchestration without expensive API calls
- Measures: "Did the code execute correctly?"

#### Gherkin Step Reference

Tactus provides a rich library of built-in steps for BDD testing. You can use these immediately in your `specifications` block:

**Tool Steps:**
```gherkin
Then the search tool should be called
Then the search tool should not be called
Then the search tool should be called at least 3 times
Then the search tool should be called exactly 2 times
Then the search tool should be called with query=test
```

**State & Stage Steps:**
```gherkin
Given the procedure has started
Then the stage should be processing
Then the state count should be 5
Then the state error should exist
```

**Completion & Iteration Steps:**
```gherkin
Then the procedure should complete successfully
Then the procedure should fail
Then the total iterations should be less than 10
Then the agent should take at least 3 turns
```

**Custom Steps:**
Define your own steps in Lua:
```lua
step("the research quality is high", function()
  local results = State.get("results")
  assert(#results > 5, "Not enough results")
end)
```

See [tactus/testing/README.md](tactus/testing/README.md) for the complete reference.

#### Evaluations: Testing Agent Intelligence

**What it tests:** The probabilistic quality of LLM outputs—whether agents produce correct, helpful, and consistent results.

**When to use:**
- Simple "LLM wrapper" procedures (minimal orchestration logic)
- Measuring output quality (accuracy, tone, format)
- Testing prompt effectiveness
- Consistency across multiple runs
- Procedures where the *intelligence* is more important than the *orchestration*

**How it works:**
```lua
evaluations {
  runs = 10,  -- Run each test case 10 times
  parallel = true,
  
  dataset = {
    {
      name = "greeting_task",
      inputs = {task = "Greet Alice warmly"}
    },
    {
      name = "haiku_task",
      inputs = {task = "Write a haiku about AI"}
    }
  },
  
  evaluators = {
    -- Check for required content
    {
      type = "contains",
      field = "output",
      value = "TASK_COMPLETE:"
    },
    
    -- Use LLM to judge quality
    {
      type = "llm_judge",
      rubric = [[
Score 1.0 if the agent:
- Completed the task successfully
- Produced high-quality output
- Called the done tool appropriately
Score 0.0 otherwise.
      ]],
      model = "openai:gpt-4o-mini"
    }
  }
}
```

**Key characteristics:**
- Uses Pydantic AI Evals framework
- Runs with `tactus eval`
- Uses real LLM calls (not mocked)
- Probabilistic: same input → potentially different outputs
- Slower: makes actual API calls
- Measures: "Did the AI produce good results?"
- Provides success rates, consistency metrics, and per-task breakdowns

#### When to Use Which?

| Feature | Behavior Specifications (BDD) | Evaluations |
|---------|-------------------------------|-------------|
| **Goal** | Verify deterministic logic | Measure probabilistic quality |
| **Command (Single)** | `tactus test` | `tactus eval` |
| **Command (Repeat)** | `tactus test --runs 10` (consistency check) | `tactus eval --runs 10` |
| **Execution** | Fast, mocked (optional) | Slow, real API calls |
| **Syntax** | Gherkin (`Given`/`When`/`Then`) | Lua configuration table |
| **Example** | "Did the agent call the tool?" | "Did the agent write a good poem?" |
| **Best for** | Complex orchestration, state management | LLM output quality, prompt tuning |

**Use Behavior Specifications when:**
- You have complex orchestration logic to test
- You need fast, deterministic tests
- You want to verify control flow (loops, conditionals, state)
- You're testing multi-agent coordination patterns
- Example: [`examples/20-bdd-complete.tac`](examples/20-bdd-complete.tac)

**Use Evaluations when:**
- Your procedure is mostly an LLM call wrapper
- You need to measure output quality (accuracy, tone)
- You want to test prompt effectiveness
- You need consistency metrics across runs
- Example: [`examples/36-eval-advanced.tac`](examples/36-eval-advanced.tac)

**Use Both when:**
- You have complex orchestration AND care about output quality
- Run BDD tests for fast feedback on logic
- Run evaluations periodically to measure LLM performance
- Example: [`examples/37-eval-comprehensive.tac`](examples/37-eval-comprehensive.tac)

**The key insight:** Behavior specifications test your *code*. Evaluations test your *AI*. Most real-world procedures need both.

#### Gherkin Step Reference

Tactus provides a rich library of built-in steps for BDD testing. You can use these immediately in your `specifications` block:

**Tool Steps:**
```gherkin
Then the search tool should be called
Then the search tool should not be called
Then the search tool should be called at least 3 times
Then the search tool should be called exactly 2 times
Then the search tool should be called with query=test
```

**State & Stage Steps:**
```gherkin
Given the procedure has started
Then the stage should be processing
Then the state count should be 5
Then the state error should exist
```

**Completion & Iteration Steps:**
```gherkin
Then the procedure should complete successfully
Then the procedure should fail
Then the total iterations should be less than 10
Then the agent should take at least 3 turns
```

**Custom Steps:**
Define your own steps in Lua:
```lua
step("the research quality is high", function()
  local results = State.get("results")
  assert(#results > 5, "Not enough results")
end)
```

See [tactus/testing/README.md](tactus/testing/README.md) for the complete reference.

#### Advanced Evaluation Features

Tactus evaluations support powerful features for real-world testing:

**External Dataset Loading:**

Load evaluation cases from external files for better scalability:

```lua
evaluations {
  -- Load from JSONL file (one case per line)
  dataset_file = "data/eval_cases.jsonl",
  
  -- Can also include inline cases (combined with file)
  dataset = {
    {name = "inline_case", inputs = {...}}
  },
  
  evaluators = {...}
}
```

Supported formats: `.jsonl`, `.json` (array), `.csv`

**Trace Inspection:**

Evaluators can inspect execution internals beyond just inputs/outputs:

```lua
evaluators = {
  -- Verify specific tool was called
  {
    type = "tool_called",
    value = "search",
    min_value = 1,
    max_value = 3
  },
  
  -- Check agent turn count
  {
    type = "agent_turns",
    field = "researcher",
    min_value = 2,
    max_value = 5
  },
  
  -- Verify state variable
  {
    type = "state_check",
    field = "research_complete",
    value = true
  }
}
```

**Advanced Evaluator Types:**

```lua
evaluators = {
  -- Regex pattern matching
  {
    type = "regex",
    field = "phone",
    value = "\\(\\d{3}\\) \\d{3}-\\d{4}"
  },
  
  -- JSON schema validation
  {
    type = "json_schema",
    field = "data",
    value = {
      type = "object",
      properties = {
        name = {type = "string"},
        age = {type = "number"}
      },
      required = {"name"}
    }
  },
  
  -- Numeric range checking
  {
    type = "range",
    field = "score",
    value = {min = 0, max = 100}
  }
}
```

**CI/CD Thresholds:**

Define quality gates that fail the build if not met:

```lua
evaluations {
  dataset = {...},
  evaluators = {...},
  
  -- Quality thresholds for CI/CD
  thresholds = {
    min_success_rate = 0.90,  -- Fail if < 90% pass
    max_cost_per_run = 0.01,  -- Fail if too expensive
    max_duration = 10.0,      -- Fail if too slow (seconds)
    max_tokens_per_run = 500  -- Fail if too many tokens
  }
}
```

When thresholds are not met, `tactus eval` exits with code 1, enabling CI/CD integration.

**See examples:**
- [`examples/34-eval-dataset.tac`](examples/34-eval-dataset.tac) - External dataset loading
- [`examples/35-eval-trace.tac`](examples/35-eval-trace.tac) - Trace-based evaluators
- [`examples/36-eval-advanced.tac`](examples/36-eval-advanced.tac) - Regex, JSON schema, range
- [`examples/33-eval-thresholds.tac`](examples/33-eval-thresholds.tac) - CI/CD quality gates
- [`examples/37-eval-comprehensive.tac`](examples/37-eval-comprehensive.tac) - All features combined

### Multi-Model and Multi-Provider Support

Use different models and providers for different tasks within the same workflow. **Every agent must specify a `provider:`** (either directly or via `default_provider:` at the procedure level).

**Supported providers:** `openai`, `bedrock`

**Mix models for different capabilities:**

```lua
Agent "researcher" {
  provider = "openai",
  model = "gpt-4o",  -- Use GPT-4o for complex research
  system_prompt = "Research the topic thoroughly...",
  tools = {"search", "done"}
})

Agent "summarizer" {
  provider = "openai",
  model = "gpt-4o-mini",  -- Use GPT-4o-mini for simple summarization
  system_prompt = "Summarize the findings concisely...",
  tools = {"done"}
})
```

**Mix providers (OpenAI + Bedrock):**

```lua
Agent "openai_analyst" {
  provider = "openai",
  model = "gpt-4o",
  system_prompt = "Analyze the data...",
  tools = {"done"}
})

Agent "bedrock_reviewer" {
  provider = "bedrock",
  model = "anthropic.claude-3-5-sonnet-20240620-v1:0",
  system_prompt = "Review the analysis...",
  tools = {"done"}
})
```

**Configure model-specific parameters:**

```lua
Agent "creative_writer" {
  provider = "openai",
  model = {
    name = "gpt-4o",
    temperature = 0.9,  -- Higher creativity
    max_tokens = 2000
  },
  system_prompt = "Write creatively...",
  tools = {"done"}
})

Agent "reasoning_agent" {
  provider = "openai",
  model = {
    name = "gpt-5",  -- Reasoning model
    openai_reasoning_effort = "high",
    max_tokens = 4000
  },
  system_prompt = "Solve this complex problem...",
  tools = {"done"}
})
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

```lua
Agent "worker" {
  system_prompt = "Process the task...",
  tools = {"search", "analyze", "done"},

  -- Control what this agent sees
  filter = {
    class = "ComposedFilter",
    chain = {
      {
        class = "TokenBudget",
        max_tokens = 120000
      },
      {
        class = "LimitToolResults",
        count = 2  -- Only show last 2 tool results
      }
    }
  }
})
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

### Advanced HITL Patterns

Beyond the omnichannel HITL described earlier, Tactus provides detailed primitives for human oversight and collaboration. You can request approval, input, or review at any point in your workflow.

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

**Declare HITL points for reusable workflows:**

```lua
hitl("confirm_publish", {
  type = "approval",
  message = "Publish this document to production?",
  timeout = 3600,
  default = false
})
```

Then reference them in your procedure:

```lua
local approved = Human.approve("confirm_publish")
```

### Cost Tracking & Metrics

Tactus provides **comprehensive cost and performance tracking** for all LLM calls. Every agent interaction is monitored with detailed metrics, giving you complete visibility into costs, performance, and behavior.

**Real-time cost reporting:**

```
💰 Cost researcher: $0.000375 (250 tokens, gpt-4o-mini, 1.2s)
💰 Cost summarizer: $0.000750 (500 tokens, gpt-4o, 2.1s)

✓ Procedure completed: 2 iterations, 3 tools used

💰 Cost Summary
  Total Cost: $0.001125
  Total Tokens: 750
  
  Per-call breakdown:
    researcher: $0.000375 (250 tokens, 1.2s)
    summarizer: $0.000750 (500 tokens, 2.1s)
```

**Comprehensive metrics tracked:**

- **Cost**: Prompt cost, completion cost, total cost (calculated from model pricing)
- **Tokens**: Prompt tokens, completion tokens, total tokens, cached tokens
- **Performance**: Duration, latency (time to first token)
- **Reliability**: Retry count, validation errors
- **Efficiency**: Cache hits, cache savings
- **Context**: Message count, new messages per turn
- **Metadata**: Request ID, model version, temperature, max tokens

**Visibility everywhere:**

- **CLI**: Real-time cost logging per call + summary at end
- **IDE**: Collapsible cost events with primary metrics visible, detailed metrics expandable
- **Tests**: Cost tracking during test runs
- **Evaluations**: Aggregate costs across multiple runs

**Collapsible IDE display:**

The IDE shows a clean summary by default (agent, cost, tokens, model, duration) with a single click to expand full details including cost breakdown, performance metrics, retry information, cache statistics, and request metadata.

This helps you:
- **Optimize costs**: Identify expensive agents and calls
- **Debug performance**: Track latency and duration issues
- **Monitor reliability**: See retry patterns and validation failures
- **Measure efficiency**: Track cache hit rates and savings

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

## Related Projects

The AI agent space is crowded. This section explains how Tactus differs from alternatives and why you might choose it.

**Tactus's core differentiator**: Most frameworks embed orchestration in Python (or another host language). Tactus uses a dedicated DSL (Lua) that is token-efficient, sandboxed, and designed to be readable and modifiable by AI agents themselves. This enables self-evolution patterns where agents can inspect and rewrite their own workflow definitions—a capability that's difficult when logic is scattered across Python classes.

### DSPy

[DSPy](https://dspy.ai) (Declarative Self-improving Python) treats prompting as a compilation target. You define typed signatures and let optimizers automatically discover effective prompts, few-shot examples, or fine-tuning strategies. DSPy excels at tasks where you have training data and clear metrics—classification, RAG, information extraction—and want to programmatically iterate on prompt quality without manual tuning.

Tactus takes a different approach: rather than optimizing prompts automatically, it provides a token-efficient, sandboxed language that serves as a safe platform for user-contributed or AI-generated code. Where DSPy hides control flow behind module composition, Tactus makes it explicit—you write the loops, conditionals, and error handling while agents handle intelligence within each turn.

The frameworks are complementary: you could use DSPy to optimize the prompts that go into a Tactus agent's `system_prompt`, then use Tactus to orchestrate those optimized agents in a durable, human-in-the-loop workflow.

| | DSPy | Tactus |
|-|------|--------|
| **Core idea** | Programming, not prompting | Token-efficient, AI-manipulable orchestration language |
| **Optimization** | Automatic (optimizers) | Manual or agent-driven self-evolution |
| **Control flow** | Declarative composition | Imperative Lua DSL |
| **Human-in-the-loop** | Not built-in | First-class citizen |
| **Durability** | Caching | Checkpointing + replay |
| **Target** | Researchers optimizing prompts | Engineers building production workflows |

### LangGraph

[LangGraph](https://github.com/langchain-ai/langgraph) is LangChain's graph-based workflow engine. Like Tactus, it emphasizes explicit control flow over autonomous agent behavior—you define nodes, edges, and state transitions rather than letting agents decide what to do next.

The key difference is the host language. LangGraph embeds workflows in Python using a `StateGraph` API, while Tactus uses Lua. This matters for two reasons: (1) Lua is more token-efficient when included in LLM context, and (2) Lua's sandboxed execution makes it safer for AI-generated or user-contributed code. If you need agents to read, understand, and modify their own orchestration logic, a dedicated DSL is more tractable than Python class hierarchies.

| | LangGraph | Tactus |
|-|-----------|--------|
| **Orchestration language** | Python (StateGraph API) | Lua DSL |
| **State management** | Explicit, graph-based | Explicit, imperative |
| **HITL** | Interrupt nodes + persistent state | First-class primitives (`Human.approve()`, etc.) |
| **Self-evolution** | Difficult (logic in Python) | Designed for it (logic in readable DSL) |
| **Ecosystem** | LangChain integration | Standalone, uses Pydantic-AI |

### CrewAI

[CrewAI](https://github.com/crewAIInc/crewAI) takes a role-based approach where agents are modeled as team members with specific responsibilities. You define a "crew" of agents with roles, goals, and backstories, then let them collaborate on tasks.

This paradigm is intuitive for certain use cases, but it imposes a specific mental model. All naming, configuration, and documentation is built around the crew/worker metaphor. If you want that structure, CrewAI provides it out of the box. If you find it constraining—or want your orchestration logic to be AI-readable without anthropomorphic abstractions—Tactus offers more flexibility.

CrewAI recently added "Flows" for more explicit control, narrowing the gap with graph-based frameworks. But the underlying paradigm remains role-centric rather than workflow-centric.

### Vendor Frameworks

The major AI companies have released their own agent frameworks:

- **[OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)** — Production evolution of OpenAI Swarm. Lightweight primitives (Agents, Handoffs, Guardrails) for multi-agent orchestration. Tightly coupled to OpenAI's ecosystem.

- **[Google ADK](https://google.github.io/adk-docs/)** (Agent Development Kit) — Modular framework with workflow agents (Sequential, Parallel, Loop) and LLM agents. Optimized for Gemini and Vertex AI deployment.

- **[Microsoft AutoGen](https://github.com/microsoft/autogen)** — Conversation-driven multi-agent framework where agents coordinate through message passing.

- **[Meta Llama Stack](https://ai.meta.com/blog/meta-llama-3-1/)** — Standardized interfaces for building agentic applications with Llama models. More of an API specification than a workflow framework.

These frameworks are valuable if you're committed to a specific vendor's ecosystem. Tactus is model-agnostic (via Pydantic-AI) and designed to run anywhere—local, cloud, or AWS Lambda Durable Functions.

### Other Tools

- **[Pydantic-AI](https://github.com/pydantic/pydantic-ai)** — Type-safe LLM integration that Tactus uses under the hood. Tactus adds orchestration, HITL, and durability on top.

- **[Guidance](https://github.com/guidance-ai/guidance)** (Microsoft) — Interleaves constrained generation with control flow. Focuses on token-level control during generation rather than workflow orchestration.

## Complete Feature List

- **Durable Execution**: Automatic position-based checkpointing for all operations (agent turns, model predictions, sub-procedure calls, HITL interactions) with replay-based recovery—resume from exactly where you left off after crashes, timeouts, or pauses
- **Model Primitive**: First-class support for ML inference (PyTorch, HTTP, HuggingFace Transformers) with automatic checkpointing—distinct from conversational agents for classification, prediction, and transformation tasks
- **Script Mode**: Write procedures without explicit `main` definitions—top-level `input`/`output` declarations and code automatically wrapped as the main procedure
- **State Management**: Typed, schema-validated persistent state with automatic initialization from defaults and runtime validation
- **Explicit Checkpoints**: Manual `checkpoint()` primitive for saving state at strategic points without suspending execution
- **Imperative Lua DSL**: Define agent workflows with full programmatic control using a token-efficient, sandboxed language designed for AI manipulation
- **Multi-Provider Support**: Use OpenAI and AWS Bedrock models in the same workflow
- **Multi-Model Support**: Different agents can use different models (GPT-4o, Claude, etc.)
- **Human-in-the-Loop**: Built-in support for human approval, input, and review with automatic checkpointing
- **Cost & Performance Tracking**: Granular tracking of costs, tokens, latency, retries, cache usage, and comprehensive metrics per agent and procedure
- **BDD Testing**: First-class Gherkin specifications for testing agent behavior
- **Asynchronous Execution**: Native async I/O for efficient LLM workflows
- **Context Engineering**: Fine-grained control over conversation history per agent
- **Typed Input/Output**: JSON Schema validation with UI generation support using `input`/`output`/`state` declarations
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

### Running Procedures

```bash
# Run a procedure
tactus run workflow.tac

# Run with parameters (supports all types)
tactus run workflow.tac --param name="Alice" --param count=5
tactus run workflow.tac --param enabled=true --param items='[1,2,3]'
tactus run workflow.tac --param config='{"key":"value","nested":{"data":true}}'

# Interactive mode - prompts for all inputs with confirmation
tactus run workflow.tac --interactive

# Missing required inputs will prompt automatically
tactus run workflow.tac  # If procedure has required inputs, you'll be prompted

# Use file storage (instead of memory)
tactus run workflow.tac --storage file --storage-path ./data
```

The CLI automatically parses parameter types:
- **Strings**: Direct values or quoted strings
- **Numbers**: Integers or floats are auto-detected
- **Booleans**: `true`, `false`, `yes`, `no`, `1`, `0`
- **Arrays**: JSON arrays like `'[1,2,3]'` or comma-separated `"a,b,c"`
- **Objects**: JSON objects like `'{"key":"value"}'`

When you run a procedure, you'll see real-time execution output:

```
Running procedure: workflow.tac (lua format)

→ Agent researcher: Waiting for response...
Hello! I'll help you with that task.
✓ Agent researcher: Completed 1204ms
→ Tool done {"reason": "Task completed successfully"}
  Result: Done
$ Cost researcher: $0.001267 (354 tokens, openai:gpt-4o, 1204ms)

✓ Procedure completed: 1 iterations, 1 tools used

$ Cost Summary
  Total Cost: $0.001267
  Total Tokens: 354
```

### Inspecting Procedures

```bash
# View procedure metadata (agents, tools, parameters, outputs)
tactus info workflow.tac
```

Example output:

```
Procedure info: workflow.tac

Parameters:
  task: string (required)
  count: number default: 3

Outputs:
  result: string (required) - Summary of the completed work

Agents:
  researcher:
    Provider: openai
    Model: gpt-4o
    Tools: search, analyze, done
    Prompt: You are a research assistant...
```

### Validation and Testing

```bash
# Validate syntax and structure
tactus validate workflow.tac

# Run BDD specifications
tactus test workflow.tac

# Test consistency across multiple runs
tactus test workflow.tac --runs 10

# Evaluate with Pydantic AI Evals
tactus eval workflow.tac --runs 10
```

### Understanding Output

The CLI displays several types of events:

- **→ Agent [name]**: Agent is processing (starts with → symbol)
- **✓ Agent [name]**: Agent completed (shows duration)
- **→ Tool [name]**: Tool was called (shows arguments and result)
- **$ Cost [name]**: Cost breakdown (tokens, model, duration)

All commands that execute workflows display comprehensive cost and performance metrics.

## Tactus IDE

Tactus includes a full-featured IDE for editing `.tac` files with instant feedback and intelligent code completion.

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

# See tactus/testing/README.md for detailed testing documentation
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
