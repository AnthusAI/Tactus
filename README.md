# Tactus

**Tactus**: A durable, token-efficient programming language for AI agents that never lose their place.

## A Programming Language for Agents

**Why do we need a special programming language for agents? Can't we just use LangGraph, Pydantic AI, Google ADK, or another agent framework?**

The answer lies in a fundamental architectural challenge: Unlike traditional programs that run continuously from start to finish, AI agents must be able to **suspend execution and wait**—for human approval, for external reviews, for asynchronous events. This requires a runtime that can pause mid-execution, persist complete state, and resume exactly where it left off.

**Consider this simple agent workflow:**

```lua
-- Tactus: Simple and durable
repeat
    Researcher.turn()

    if Tool.called("expensive_analysis") then
        local approved = Human.approve({message = "Review results?"})
        if not approved then return {rejected = true} end
    end
until Tool.called("done")
```

**Now try implementing this in any general-purpose language (Python, JavaScript, Go, etc.).** You immediately face problems:

1. **Where does execution pause?** `Human.approve()` needs to suspend the entire workflow, save state, and return control to your web server
2. **How do you serialize the call stack?** Most language runtimes don't support serializing execution state—you can't just `pickle.dump(locals())`
3. **How do you restore context?** When the human responds, you need to reconstruct: the agent's conversation history, the loop iteration, the conditional branch, local variables
4. **How do you avoid duplicate work?** Re-running from the start means re-calling the LLM, re-running the expensive analysis tool

**The framework solution requires building your own runtime:**
- Manual state machine with explicit states (`AWAITING_TOOL`, `AWAITING_APPROVAL`, etc.)
- Serialization layer for conversation history, tool results, loop counters
- Replay logic to skip already-completed operations
- Coordination between your application framework and agent execution

**This is what existing agent frameworks force you to build yourself.** Whether LangGraph's state graphs, Pydantic AI's workflows, or Google ADK's agents—they all require you to manually manage state persistence and resumption.

**Tactus provides this runtime as a language feature.** Every operation is automatically checkpointed. Suspension and resumption are transparent. Your workflow logic stays simple and readable—no manual state machines, no serialization code, no replay logic.

**When the workflow pauses for human approval?** It resumes from that exact point. The agent conversation, tool calls, and human decision are all preserved. No wasted tokens, no duplicate work.

**Why this enables omni-channel deployment:** Because your workflow logic is defined once in a token-efficient Lua file and plugged into any application—web apps, mobile apps, chat systems, voice interfaces. The durable runtime handles suspension and resumption transparently, making agents first-class citizens in larger systems. You write the agent logic once; the runtime adapts it to any channel.

Your entire workflow—agents, logic, data transformations—lives in one sandboxed Lua file that's:

- **Durable**: Automatic checkpointing + replay for agent turns, model inference, sub-procedures, HITL
- **Portable**: Deploy the same workflow across channels without rewriting
- **Safe**: Sandboxed VM that only accesses the tools you explicitly grant
- **Token-efficient**: Simple Lua syntax with minimal noise—perfect for feeding back into LLM context
- **Self-modifiable**: Agents can read and rewrite their own workflow definitions for self-evolution
- **Verifiable**: First-class BDD testing and ML evaluations built into the language

## Quick Start

### Installation

```bash
pip install tactus
```

### Your First Procedure: Hello and Done

Here's a complete working example that demonstrates the core concepts of Tactus. We define an agent with a goal and a tool, orchestrate with Lua, and include a test specification.

Create a file `hello.tac`:

```lua
agent("greeter", {
  provider = "openai",
  model = "gpt-4o-mini",

  system_prompt = [[
    You are a friendly greeter. Greet the user by name: {input.name}
    When done, call the done tool.
  ]],

  initial_message = "Please greet the user.",

  tools = {"done"}
})

procedure({
  input = {
    name = {
      type = "string",
      default = "World"
    }
  },

  output = {
    completed = {
      type = "boolean",
      required = true
    },
    greeting = {
      type = "string",
      required = true
    }
  },

  state = {}
}, function()
  -- Loop until the agent decides to use the 'done' tool
  repeat
    Greeter.turn()  -- Give the agent a turn to think and act
  until Tool.called("done")

  -- Return the result captured from the tool call
  return {
    completed = true,
    greeting = Tool.last_call("done").args.reason
  }
end)

specifications([[
Feature: Greeting Workflow

  Scenario: Agent greets user and completes
    Given the procedure has started
    When the greeter agent takes turns
    Then the done tool should be called exactly once
    And the procedure should complete successfully
    And the output completed should be True
    And the output greeting should exist
]])
```

**Run the procedure:**

```bash
export OPENAI_API_KEY=your-key
tactus run hello.tac
```

**Test the procedure to verify behavior:**

```bash
tactus test hello.tac
```

This runs the Gherkin specification and verifies that the agent behaves correctly. You'll see output like:

```
Feature: Greeting Workflow
  Scenario: Agent greets user and completes ... passed
```

**Evaluate consistency across multiple runs:**

```bash
tactus test hello.tac --runs 10
```

This runs the test 10 times and reports success rate and consistency metrics, helping you identify flaky behavior.

**What's happening here:**

1. **Agents** (top level): Define reusable agents with models, prompts, and tools. When you define an agent named `greeter`, the primitive `Greeter.turn()` becomes available in Lua.

2. **Procedure** with config: Takes two arguments:
   - **Config table**: Contains `input` (inputs), `output` (validated return values), and `state` (persistent working data)
   - **Function**: Your workflow logic in Lua with explicit control flow

3. **Input Parameters** (`input`): Define typed inputs with defaults. These can be overridden at runtime and are available in templates as `{input.name}`.

4. **Output Schema** (`output`): Define the structure of return values. Tactus validates that your procedure returns the declared fields with correct types.

5. **State Schema** (`state`): Define persistent working variables with types and defaults. State is preserved across checkpoints.

6. **Specifications** (`specifications`): Gherkin BDD tests that verify your agent's behavior. These are first-class citizens in Tactus—you can run them with `tactus test` or evaluate consistency with `tactus evaluate`.

**Key insight:** Input, output, and state are defined *inside* the procedure config because they belong to the procedure. Agents are defined at the top level because they're reusable across procedures.

## Key Features

### Programmatic Orchestration (Lua)

Tactus is a **new programming language** for AI agents. Unlike rigid configuration files, Tactus programs are written in Lua, giving you full programmatic control over execution flow. A Tactus program isn't just a script—it's a defined unit of work with declared **inputs (parameters)** and **outputs**.

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

**Why Lua?**

Most agent frameworks rely on Python (e.g., LangChain, CrewAI). While powerful, Python presents challenges for autonomous agents: it is difficult to sandbox, its significant whitespace is fragile when generated by AI, and it carries a lot of syntactic noise.

Tactus moves agent logic into a **DSL built on Lua** to solve these problems:

-   **Sandboxed & Safe**: Tactus agents run in a secure VM designed for isolation. Unlike Python, which exposes the host system, Tactus procedures can only access what you explicitly grant them.
-   **Malleable "Agent as Code"**: Lua's syntax is simple and robust, lacking Python's delicate whitespace requirements. This makes it safe for AI models to generate and modify their own code.
-   **High Signal-to-Noise**: The DSL is optimized for agent development. The code is concise and token-efficient, making it ideal for feeding back into an LLM's context window for self-evolution.
-   **Introspection**: A Tactus program is a structured document, not just an opaque script. The custom parser allows external tools to analyze, visualize, and build UIs for a procedure *without running it*.
-   **Explicit Control**: You get standard programming constructs (loops, conditionals, error handling) rather than hidden planning logic.

This introspection capability enables the next feature: the ability to define a rigorous **interface contract** that any application can read.

### Per-Turn Tool Control

Tactus gives you fine-grained control over what tools an agent has access to on each individual turn. This enables powerful patterns like **tool result summarization**, where you want the agent to explain what a tool returned without having access to call more tools.

**The Pattern:**

```lua
agent("researcher", {
  provider = "openai",
  model = "gpt-4o",
  system_prompt = "You are a research assistant.",
  tools = {"search", "analyze", "done"}
})

procedure({}, function()
  repeat
    -- Main turn: agent has all tools
    Researcher.turn()
    
    -- After each tool call, ask agent to summarize with NO tools
    if Tool.called("search") or Tool.called("analyze") then
      Researcher.turn({
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

### MCP Server Integration

Tactus provides first-class support for [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) servers, allowing you to connect to external tool providers and use their tools in your procedures.

**Configuration** (`.tactus/config.yml`):

```yaml
mcp_servers:
  plexus:
    command: "python"
    args:
      - "-m"
      - "plexus.mcp"
    env:
      PLEXUS_ACCOUNT_KEY: "${PLEXUS_ACCOUNT_KEY}"
      PLEXUS_API_KEY: "${PLEXUS_API_KEY}"
  
  filesystem:
    command: "npx"
    args:
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
      - "/workspace"
```

**Tool Namespacing:**

Tools from MCP servers are automatically prefixed with the server name to prevent conflicts:

```lua
agent("worker", {
    provider = "openai",
    model = "gpt-4o",
    tools = {
        "plexus_score_info",           -- From plexus server
        "plexus_evaluation_run",       -- From plexus server
        "filesystem_read_file",        -- From filesystem server
        "filesystem_write_file",       -- From filesystem server
        "done"
    }
})
```

**How it works:**

1. **Stdio Transport**: Each MCP server runs as a subprocess with stdio communication
2. **Automatic Discovery**: Tools are loaded from servers at runtime
3. **Native Integration**: Uses Pydantic AI's `MCPServerStdio` under the hood
4. **Tool Tracking**: All MCP tool calls are tracked via `Tool.called()` and `Tool.last_result()`

**Environment Variables:**

Use `${VAR}` syntax in config to reference environment variables:

```yaml
mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"  # Reads from system env
```

**Multiple Servers:**

You can configure multiple MCP servers and use tools from all of them in the same procedure. Each server's tools are independently namespaced.

See `examples/40-mcp-test.tac` for a complete working example.

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

### Typed Parameters & The Contract

Parameters in Tactus are more than just variables—they form a **contract** defined by the program. Because parameters are typed and structured (strings, numbers, enums, booleans), any application can use the Tactus parser to **introspect** a program and automatically generate a UI appropriate for the channel:

*   **Mobile App**: Native forms and inputs.
*   **Chat Bot**: Interactive cards or guided conversation flows.
*   **SMS**: A structured text-based interview.
*   **Microsoft Teams**: Rich Adaptive Cards.

This separation means your agent logic remains the same, while the interface adapts to where it's running.

```lua
procedure({
  input = {
    topic = {
      type = "string",
      required = true,
      description = "The topic to research"
    },
    depth = {
      type = "string",
      enum = {"shallow", "deep"},
      default = "shallow"
    },
    max_results = {
      type = "number",
      default = 10
    },
    include_sources = {
      type = "boolean",
      default = true
    }
  },

  state = {}
}, function()
  -- Access input parameters
  local topic = input.topic
  local depth = input.depth
  -- ...
end)
```

Input parameters are accessed in templates as `{input.topic}` and in Lua as `input.topic`.

### Multi-Model and Multi-Provider Support

Use different models and providers for different tasks within the same workflow. **Every agent must specify a `provider:`** (either directly or via `default_provider:` at the procedure level).

**Supported providers:** `openai`, `bedrock`

**Mix models for different capabilities:**

```lua
agent("researcher", {
  provider = "openai",
  model = "gpt-4o",  -- Use GPT-4o for complex research
  system_prompt = "Research the topic thoroughly...",
  tools = {"search", "done"}
})

agent("summarizer", {
  provider = "openai",
  model = "gpt-4o-mini",  -- Use GPT-4o-mini for simple summarization
  system_prompt = "Summarize the findings concisely...",
  tools = {"done"}
})
```

**Mix providers (OpenAI + Bedrock):**

```lua
agent("openai_analyst", {
  provider = "openai",
  model = "gpt-4o",
  system_prompt = "Analyze the data...",
  tools = {"done"}
})

agent("bedrock_reviewer", {
  provider = "bedrock",
  model = "anthropic.claude-3-5-sonnet-20240620-v1:0",
  system_prompt = "Review the analysis...",
  tools = {"done"}
})
```

**Configure model-specific parameters:**

```lua
agent("creative_writer", {
  provider = "openai",
  model = {
    name = "gpt-4o",
    temperature = 0.9,  -- Higher creativity
    max_tokens = 2000
  },
  system_prompt = "Write creatively...",
  tools = {"done"}
})

agent("reasoning_agent", {
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
agent("worker", {
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

### Gherkin BDD Testing

Tactus has **first-class support for behavior-driven testing** using Gherkin syntax. Write natural language specifications directly in your procedure files:

```lua
specifications([[
Feature: Research Task Completion

  Scenario: Agent completes basic research
    Given the procedure has started
    When the researcher agent takes turns
    Then the search tool should be called at least once
    And the done tool should be called exactly once
    And the procedure should complete successfully
]])
```

**Run tests:**
```bash
# Run all scenarios once
tactus test procedure.tac

# Evaluate consistency (run 10 times per scenario)
tactus test procedure.tac --runs 10
```

**Evaluation output:**
```
Scenario: Agent completes basic research
  Success Rate: 90% (9/10)
  Duration: 1.23s (±0.15s)
  Consistency: 90%
  ⚠️  FLAKY - Inconsistent results detected
```

The framework provides rich built-in steps for testing Tactus primitives (tools, stages, state, iterations) and supports custom Lua step definitions. Tests run in parallel for fast feedback, and evaluations measure consistency and reliability across multiple runs.

See [tactus/testing/README.md](tactus/testing/README.md) for complete documentation.

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

```bash
# Run a workflow (displays real-time cost tracking and summary)
tactus run workflow.tac
tactus run workflow.tac --param task="Analyze data"

# Validate a workflow
tactus validate workflow.tac

# Test a workflow (run Gherkin specifications with cost tracking)
tactus test workflow.tac

# Evaluate consistency across multiple runs (includes cost metrics)
tactus evaluate workflow.tac --runs 10
```

All commands that execute workflows display comprehensive cost and performance metrics, including per-call costs, total costs, token usage, and timing information.

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

## Defining Tools with Lua Functions

Tactus allows you to define custom tools as Lua functions directly within your `.tac` files. This gives agents the ability to perform custom operations without requiring external Python plugins or MCP servers.

### Three Approaches

**1. Individual Tools:**
```lua
tool("calculate_tip", {
    description = "Calculate tip amount",
    parameters = {
        bill = {type = "number", required = true},
        percent = {type = "number", required = true}
    }
}, function(args)
    return tostring(args.bill * args.percent / 100)
end)

agent("assistant", {
    toolsets = {"calculate_tip", "done"}
})
```

**2. Grouped Toolsets:**
```lua
toolset("math_tools", {
    type = "lua",
    tools = {
        {name = "add", parameters = {...}, handler = function(args) ... end},
        {name = "multiply", parameters = {...}, handler = function(args) ... end}
    }
})
```

**3. Inline Agent Tools:**
```lua
agent("assistant", {
    tools = {
        {name = "uppercase", parameters = {...}, handler = function(args) ... end}
    },
    toolsets = {"done"}
})
```

**Learn more:** See [docs/TOOLS.md](docs/TOOLS.md) for comprehensive documentation with examples and best practices.

## Documentation

- [**Specification (DSL Reference)**](SPECIFICATION.md) - The official specification for the Tactus domain-specific language.
- [**Tools Guide**](docs/TOOLS.md) - Comprehensive guide to defining tools with Lua functions.
- [**Implementation Guide**](IMPLEMENTATION.md) - Maps the specification to the actual codebase implementation. Shows where each feature is implemented, what's complete, and what's missing relative to the specification.
- [**Testing Strategy**](tactus/testing/README.md) - Testing approach, frameworks, and guidelines for adding new tests.
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
